from backend.repositories.subject_repository import get_or_create_subject


def _safe_date(value):
    if not value:
        return None
    val_str = str(value).strip()
    if not val_str or val_str.lower() in ("null", "none"):
        return None
    if len(val_str) >= 10 and val_str[2] == "." and val_str[5] == ".":
        try:
            return f"{val_str[6:10]}-{val_str[3:5]}-{val_str[0:2]}"
        except Exception:
            pass
    return val_str

def extract_clean_address(address_field):
    """Розбирає вкладені структури адреси з JSON та повертає чистий текст."""
    if not address_field:
        return None
    if isinstance(address_field, str):
        return address_field.strip()
    if isinstance(address_field, list):
        parts = []
        for item in address_field:
            if isinstance(item, dict):
                for val in item.values():
                    if val and isinstance(val, str):
                        parts.append(val.strip())
            elif isinstance(item, str):
                parts.append(item.strip())
        return ", ".join(parts) if parts else None
    return str(address_field)

def process_rrp(cursor, check_id, item_data):
    """
    Парсинг и сохранение данных ДРРП (Сводная информация + Расширенная)
    с защитой от аномальных типов данных (строки вместо массивов/объектов)
    """
    if not item_data:
        return

    plot_node = item_data.get("Plot") or {}

    # --- ЧАСТЬ 1: СВОДНАЯ ИНФОРМАЦИЯ (rrpLandInfo) ---
    rrp_sum = plot_node.get("rrpLandInfo") or {}
    if isinstance(rrp_sum, dict) and rrp_sum:
        rent = rrp_sum.get("rent") or {}
        if not isinstance(rent, dict):
            rent = {}

        cursor.execute(
            """
            INSERT INTO PlotRrpSummarySnapshot (
                CheckId, Area, IrpsRegDate, RentStartDate, RentEndDate, SumRent
            ) OUTPUT INSERTED.SummarySnapshotId VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                check_id,
                rrp_sum.get("area"),
                _safe_date(rrp_sum.get("irpsRegDate")),
                _safe_date(rent.get("startDate")),
                _safe_date(rent.get("endDate")),
                rent.get("sumRent"),
            ),
        )
        summary_id = cursor.fetchone()[0]

        subjects = rrp_sum.get("subject") or []
        if isinstance(subjects, list):
            for sbj in subjects:
                if not isinstance(sbj, dict):
                    continue
                cursor.execute(
                    """
                    INSERT INTO PlotRrpSummarySubjects (SummarySnapshotId, Name, SbjRlName, Code, SbjType, IsOwner)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        summary_id,
                        sbj.get("name"),
                        sbj.get("sbjRlName"),
                        sbj.get("code"),
                        sbj.get("type"),
                        sbj.get("isOwner"),
                    ),
                )

    # --- ЧАСТЬ 2: РАСШИРЕННАЯ ИНФОРМАЦИЯ (RrpAdvanced) ---
    adv = item_data.get("RrpAdvanced") or {}
    if not isinstance(adv, dict) or not adv:
        return

    def _insert_docs(parent_id, parent_type, docs):
        if not docs:
            return

        # Если API вернуло строку вместо массива документов
        if isinstance(docs, str):
            cursor.execute(
                """
                INSERT INTO RrpCauseDocuments (ParentId, ParentType, CdType)
                VALUES (?, ?, ?)
            """,
                (parent_id, parent_type, docs),
            )
            return

        # Нормальная обработка массива
        if isinstance(docs, list):
            for d in docs:
                if not isinstance(d, dict):
                    continue
                cursor.execute(
                    """
                    INSERT INTO RrpCauseDocuments (ParentId, ParentType, CdType, CdTypeExtension, DocNumber, DocDate, Publisher)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        parent_id,
                        parent_type,
                        d.get("cdType"),
                        d.get("cdTypeExtension"),
                        d.get("enum"),
                        _safe_date(d.get("docDate")),
                        d.get("publisher"),
                    ),
                )

    # Обработка объектов недвижимости
    realty_list = adv.get("realty") or []
    if not isinstance(realty_list, list):
        return

    for realty in realty_list:
        if not isinstance(realty, dict):
            continue

        cursor.execute(
            """
            INSERT INTO RrpRealtySnapshot (CheckId, RealtyNumber, RegistrationNumber, RegistrationDate, ReType, ReState, RealtyAddress)
            OUTPUT INSERTED.RealtyId VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                check_id,
                realty.get("regNum"),
                realty.get("regNum"),
                _safe_date(realty.get("regDate")),
                realty.get("reType"),
                realty.get("reState"),
                extract_clean_address(realty.get("realtyAddress")),
            ),
        )
        realty_id = cursor.fetchone()[0]

        ground_areas = realty.get("groundArea") or []
        if isinstance(ground_areas, list):
            for ga in ground_areas:
                if not isinstance(ga, dict):
                    continue
                cursor.execute(
                    "INSERT INTO RrpRealtyGroundArea (RealtyId, Area, AreaUM) VALUES (?, ?, ?)",
                    (realty_id, ga.get("area"), ga.get("areaUM")),
                )

        # --- СОБСТВЕННОСТЬ ---
        properties = realty.get("properties") or []
        if isinstance(properties, list):
            for prop in properties:
                if not isinstance(prop, dict):
                    continue

                subjects = prop.get("subjects") or [{}]
                if not isinstance(subjects, list):
                    subjects = [{}]

                for sbj in subjects:
                    if not isinstance(sbj, dict):
                        continue
                    subj_id = get_or_create_subject(
                        cursor,
                        sbj.get("sbjCode"),
                        sbj.get("sbjName") or sbj.get("sbjRlName") or "Не вказано",
                        sbj.get("dcSbjType"),
                    )

                    cursor.execute(
                        """
                        INSERT INTO RrpPropertyRights (RealtyId, SubjectId, RightType, RegistrationNumber, RegistrationDate, PartSize, PrState, Registrar)
                        OUTPUT INSERTED.Id VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            realty_id,
                            subj_id,
                            prop.get("prKind"),
                            prop.get("rnNum"),
                            _safe_date(prop.get("regDate")),
                            prop.get("partSize"),
                            prop.get("prState"),
                            prop.get("registrar"),
                        ),
                    )
                    _insert_docs(cursor.fetchone()[0], "PROPERTY", prop.get("causeDocuments"))

        # --- АРЕНДА (Иные права) ---
        irps = realty.get("irps") or []
        if isinstance(irps, list):
            for irp in irps:
                if not isinstance(irp, dict):
                    continue

                subjects = irp.get("subjects") or [{}]
                if not isinstance(subjects, list):
                    subjects = [{}]

                for sbj in subjects:
                    if not isinstance(sbj, dict):
                        continue
                    subj_id = get_or_create_subject(
                        cursor,
                        sbj.get("sbjCode"),
                        sbj.get("sbjName") or sbj.get("sbjRlName") or "Не вказано",
                        sbj.get("dcSbjType"),
                    )

                    auto_prolong = irp.get("isAutomaticProlongation")
                    is_prolong = 1 if str(auto_prolong).lower() == "true" else 0

                    cursor.execute(
                        """
                        INSERT INTO PlotRightSnapshot (
                            RealtyId, SubjectId, RightType, RegistrationNumber, RegistrationDate,
                            ContractTerm, IsAutomaticProlongation, ObjectDescription, IrpSort
                        ) OUTPUT INSERTED.RightId VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            realty_id,
                            subj_id,
                            irp.get("IrpSort"),
                            irp.get("rnNum"),
                            _safe_date(irp.get("regDate")),
                            irp.get("contractTerm"),
                            is_prolong,
                            irp.get("objectDescription"),
                            irp.get("IrpSort"),
                        ),
                    )
                    _insert_docs(cursor.fetchone()[0], "IRP", irp.get("causeDocuments"))

        # --- ИПОТЕКИ ---
        mortgages = realty.get("mortgage") or []
        if isinstance(mortgages, list):
            for mort in mortgages:
                if not isinstance(mort, dict):
                    continue

                subjects = mort.get("subjects") or [{}]
                if not isinstance(subjects, list):
                    subjects = [{}]

                for sbj in subjects:
                    if not isinstance(sbj, dict):
                        continue
                    subj_id = get_or_create_subject(
                        cursor, sbj.get("sbjCode"), sbj.get("sbjName") or "Не вказано", sbj.get("dcSbjType")
                    )

                    cursor.execute(
                        """
                        INSERT INTO RrpMortgage (RealtyId, SubjectId, RegistrationNumber, RegistrationDate, MortgageType, PrState, ObjectDescription, Registrar)
                        OUTPUT INSERTED.MortgageId VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            realty_id,
                            subj_id,
                            mort.get("rnNum"),
                            _safe_date(mort.get("regDate")),
                            mort.get("prKind"),
                            mort.get("prState"),
                            mort.get("objectDescription"),
                            mort.get("registrar"),
                        ),
                    )
                    mort_id = cursor.fetchone()[0]
                    _insert_docs(mort_id, "MORTGAGE", mort.get("causeDocuments"))

                    obl_list = mort.get("obligation") or []
                    if isinstance(obl_list, list):
                        for obl in obl_list:
                            if not isinstance(obl, dict):
                                continue
                            cursor.execute(
                                "INSERT INTO RrpMortgageObligations (MortgageId, ObligationType, Amount, Currency) VALUES (?, ?, ?, ?)",
                                (mort_id, obl.get("oblType"), obl.get("amount"), obl.get("currency")),
                            )

        # --- ОГРАНИЧЕНИЯ (Аресты) ---
        limitations = realty.get("limitation") or []
        if isinstance(limitations, list):
            for lim in limitations:
                if not isinstance(lim, dict):
                    continue

                subjects = lim.get("subjects") or [{}]
                if not isinstance(subjects, list):
                    subjects = [{}]

                for sbj in subjects:
                    if not isinstance(sbj, dict):
                        continue
                    subj_id = get_or_create_subject(
                        cursor, sbj.get("sbjCode"), sbj.get("sbjName") or "Не вказано", sbj.get("dcSbjType")
                    )

                    cursor.execute(
                        """
                        INSERT INTO RrpLimitations (RealtyId, SubjectId, LimitationType, RegistrationNumber, RegistrationDate, LmState, ObjectDescription, Registrar)
                        OUTPUT INSERTED.LimitationId VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            realty_id,
                            subj_id,
                            lim.get("lmSort"),
                            lim.get("rnNum"),
                            _safe_date(lim.get("regDate")),
                            lim.get("lmState"),
                            lim.get("objectDescription"),
                            lim.get("registrar"),
                        ),
                    )
                    _insert_docs(cursor.fetchone()[0], "LIMITATION", lim.get("causeDocuments"))

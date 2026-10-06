# 01. Phase 1 — Multi-Agency Corpus Ingestion & Data Architecture

### Overview
Phase 1 established the legal crawling, scraping, and multi-channel statutory ingestion pipeline across all 13 Indian financial and economic regulatory bodies (RBI, SEBI, MCA, CBIC, CBDT, IBBI, EPFO, ESIC, IRDAI, PFRDA, MeitY, IFSCA) and 900+ Parliamentary Acts via IndiaCode.

### Verified Ingested Corpus (manifest.db)

| Authority / Regulator | Scope & Regulatory Domain | Verified Documents | Storage Size | Temporal Coverage |
| :--- | :--- | :---: | :---: | :---: |
| **RBI** | Central Banking, Monetary Policy, NBFCs | **14,147** | 399.97 MB | 1978 – 2026 |
| **SEBI** | Securities, Capital Markets, Mutual Funds | **2,797** | 15.64 MB | 1991 – 2026 |
| **INDIACODE** | Central Commercial & Financial Acts of Parliament | **902** | 55.97 MB | 1838 – 2026 |
| **EPFO** | Employees' Provident Fund & Pensions | **789** | 13.92 MB | 2022 – 2024 |
| **CBDT** | Income Tax Act Sections & Direct Tax Circulars | **690** | 1.67 MB | 2016 – 2025 |
| **IRDAI** | Insurance Business, Solvency & Health Norms | **683** | 5.84 MB | 2000 – 2026 |
| **MCA** | Companies Act 2013 Sections & Corporate Rules | **573** | 1.04 MB | 2013 – 2023 |
| **IFSCA** | GIFT City International Financial Services | **255** | 5.32 MB | 2015 – 2026 |
| **ESIC** | Employees' State Insurance & Social Security | **249** | 1.21 MB | 2023 – 2026 |
| **IBBI** | Insolvency & Bankruptcy Rules & Guidelines | **247** | 2.39 MB | 2016 – 2023 |
| **CCI** | Competition Act 2002 Sections & Antitrust Orders | **139** | 0.17 MB | 2003 – 2024 |
| **CBIC** | GST Acts & Rules, Customs, Advance Rulings | **116** | 2.22 MB | 2017 – 2026 |
| **MEITY** | IT Act 2000 Sections, Cyber & Intermediary Rules | **82** | 0.08 MB | 2000 – 2023 |
| **PFRDA** | National Pension System (NPS) Circulars | **36** | 0.51 MB | 2021 – 2024 |
| **TOTAL** | **All 13 Regulators + Central Acts** | **21,705** | **505.96 MB** | **1838 – 2026** |

### Multi-Channel Acquisition Architecture
1. **Direct Regulatory REST APIs**: Discovered and integrated high-throughput official endpoints (e.g., IFSCA JSON REST API `/Legal/GetLegalData` and preview viewer).
2. **Deep Web Crawlers**: Multi-page scrapers traversing official circular archives (IRDAI MD5-hashed pagination, IBBI subordinate legislation, PFRDA NPS portals).
3. **Statutory Code Deconstructors**: Section-by-section statutory parser decomposing primary enactments (Companies Act 2013, Income-Tax Act, Competition Act 2002, IT Act 2000) into atomic, citation-verifiable provisions.
4. **Parliamentary Enactment Engine**: Ingestion of all foundational financial and commercial Acts of Parliament from official IndiaCode records.
5. **Deduplicated WAL Database**: SQLite WAL schema enforcing strict `sha256` content hashing, `text_source` constraints, and temporal validity metadata.

# Phase 7 NSEDataFetcher Dependency & Environment Map

**Document Identifier:** `PHASE7_NSE_DATA_FETCHER_DEPENDENCY_MAP`
**Governing Workstream:** Milestone 4.8 Dependency Location & Licensing Inspection
**Audit Target:** `connector_review/nse_data_service.py`
**Inspected Import:** `from nse import NSE`
**Dependency Approval Decision:** `REQUIRES_DEPENDENCY_APPROVAL`
**Installation Status:** `DEPENDENCY_NOT_INSTALLED` (in Phase 7 runtime environment)

---

## 1. Import-to-Distribution Mapping

The review source `connector_review/nse_data_service.py` requires a single third-party import:
```python
from nse import NSE
```

A non-importing specification lookup across all available local Python interpreters produced the following distribution mapping:

| Attribute | Verified Value |
|---|---|
| **Python Import Name** | `nse` |
| **PyPI Distribution Name** | `nse` (also distributed with server extras as `nse[server]`) |
| **Upstream Version** | `4.0.1` |
| **Project Summary** | *Unofficial Python Api for NSE India stock exchange* |
| **Upstream Homepage** | `https://github.com/BennyThadikaran/NseIndiaApi` |
| **Author** | Benny Thadikaran |
| **License (PyPI Classifier)** | `OSI Approved :: GNU General Public License v3 (GPLv3)` |
| **License File Content** | GNU General Public License Version 3, 29 June 2007 |

---

## 2. Multi-Environment Dependency Location Audit

In strict compliance with non-execution safety rules, dependency locations were checked without importing the module:

| Python Environment | Command Executed | Result | Origin Path |
|---|---|---|---|
| **Phase 7 Runtime (Python 3.12.10)** | `.venv-phase7\Scripts\python.exe -c "import importlib.util; s=importlib.util.find_spec('nse'); print(s.origin if s else 'NOT FOUND')"` | **NOT FOUND** | None |
| **System Python 3.11** | `py -3.11 -c "import importlib.util; s=importlib.util.find_spec('nse'); print(s.origin if s else 'NOT FOUND')"` | **NOT FOUND** | None |
| **System Python 3.14** | `py -3.14 -c "import importlib.util; s=importlib.util.find_spec('nse'); print(s.origin if s else 'NOT FOUND')"` | **FOUND** | `C:\Users\r_chh\AppData\Roaming\Python\Python314\site-packages\nse\__init__.py` |

---

## 3. Local Environment Verification (`py -3.14 -m pip show nse`)

Running `pip show nse` against the Python 3.14 installation confirmed:
```text
Name: nse
Version: 4.0.1
Summary: Unofficial Python Api for NSE India stock exchange
Home-page: https://github.com/BennyThadikaran/NseIndiaApi
Author: Benny Thadikaran
Author-email:
License:
Location: C:\Users\r_chh\AppData\Roaming\Python\Python314\site-packages
Requires: httpx, mthrottle
Required-by:
```

### Transitive Dependencies
Inspection of `nse-4.0.1.dist-info\METADATA` reveals the following mandatory transitive dependencies:
- `httpx==0.28.1` (used for HTTP transport in `server=True` mode)
- `mthrottle>=0.0.1` (used by upstream to throttle requests to 3 calls/sec)
- Optional extras (`nse[server]`): `httpx[http2]==0.28.1`

---

## 4. Phase 7 Python 3.12 Runtime Status

1. **Not Installed in `.venv-phase7`:** The package is absent from the designated Phase 7 virtual environment (`Python 3.12.10`).
2. **Not Declared in `requirements-phase7.txt`:** The dependency is not registered in the project's dependency manifest.
3. **pip check Compliance:** Running `.venv-phase7\Scripts\python.exe -m pip check` confirms zero broken requirements in the current clean state.
4. **No-Install Confirmation:** In strict accordance with Milestone 4.8 prohibitions, `pip install` was **not executed**, no packages were downloaded, and no network access was attempted.

---

## 5. Licensing & Legal Risk Analysis (GPLv3)

Inspection of `nse-4.0.1.dist-info\licenses\LICENSE` confirms that `nse` is licensed under the **GNU General Public License v3.0 (GPLv3)**:
```text
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License...
```

### Strategic Integration Hazard:
- GPLv3 is a strong copyleft license. Linking proprietary software directly against a GPLv3 library can subject the combined work to GPLv3 source disclosure requirements.
- GaurviDEEP's proprietary signal algorithms, feature engineering modules, and Phase 6/7 quantitative models must not become tainted by GPLv3 copyleft provisions.
- Any future integration must either:
  1. Isolate the connector behind a process boundary (e.g., a standalone CLI sub-process or isolated local microservice communicates over JSON IPC/pipes); or
  2. Require an approved commercial license or dual-license agreement from the upstream author; or
  3. Replace the library with an Apache-2.0 / MIT alternative or custom in-house HTTP adapter.

---

## 6. Dependency Approval Decision

### Formal Classifications:
- **`INTENDED_DISTRIBUTION_CONFIRMED`** (`nse` v4.0.1 by Benny Thadikaran)
- **`DEPENDENCY_NOT_INSTALLED_IN_PHASE7_VENV`**
- **`REQUIRES_DEPENDENCY_APPROVAL`**
- **`GPLV3_LEGAL_REVIEW_REQUIRED`**

No dependency installation or environment modification is authorized during this milestone.

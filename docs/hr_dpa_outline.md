# HR Data Processing Addendum — outline (ShiftSwift HR)

**DRAFT OUTLINE — not legal advice. Review with a UK solicitor before use.**

## 1. Roles

- **Customer:** Data Controller (employer)
- **Provider / Processor:** Datasoftware Analytics Ltd (Company No. 14568900), 235 Charlbury Road, Nottingham, NG8 1NF — trading as **ShiftSwift HR**

## 2. Subject matter and duration

- Processing employee PII for HR administration for the term of the MSA + deletion period

## 3. Nature and purpose

- Storage and display of employee records, rotas, payroll data, compliance artefacts (RTW PDFs, absence alerts, SMS change logs)

## 4. Categories of data subjects

- Customer's employees, workers, and applicants

## 5. Categories of personal data

- Identity, contact, employment, salary, disciplinary, right-to-work, sponsorship status
- Where Time Clock is enabled: geolocation at punch time (coordinates, accuracy, distance from site, punch timestamps)

## 6. **Data silo / segregation (critical clause)**

> Provider operates ShiftSwift HR on infrastructure **logically and physically segregated** from Provider's hospitality commerce systems (EPOS, order logs, card-present transaction metadata). Employee HR data processed under this DPA is stored in dedicated HR tenant databases identified by `platform = hr`. **No employee HR records are commingled with EPOS sales data, kitchen order logs, or payment card data.** EPOS system availability or breach does not imply access to HR data, and vice versa.

## 7. Sub-processors

- List hosting provider, email provider, Stripe (billing metadata only — not employee HR files)

## 8. Security measures

- Encryption in transit (TLS)
- Access control, RBAC, tenant isolation
- Audit logging (`employee_data_audit_log`, `security_audit_events`)
- Reference: Cyber Essentials controls (`docs/cyber_essentials_readiness.md`)

## 9. International transfers

- UK/EEA hosting preferred; if US sub-processors used, SCCs/UK IDTA

## 10. Breach notification

- Provider notifies Customer without undue delay (target: 72 hours of becoming aware)

## 11. Data subject rights

- Provider assists Customer in responding to SARs within [reasonable period]

## 12. Deletion / return

- On termination, delete or return HR data within [30–90 days] except legal retention

## 13. Audits

- Customer may request compliance information annually; no unrestricted site audits without cause

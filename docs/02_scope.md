# Project Scope

## Version

Version 1.0 — Minimum Viable Product

## In Scope

- SAP ECC Customer Master migration
- SAP S/4HANA Business Partner target
- Excel, CSV and PDF uploads
- Data profiling
- Schema validation
- Business-rule validation
- Duplicate detection
- AI-assisted field mapping
- Human approval workflow
- Data transformation preview
- Migration-ready Excel generation
- Interactive dashboards
- PDF summary report
- RAG over migration documents
- Read-only Text-to-SQL assistant
- Deployment on AWS or Azure

## Required Input Files

- ECC_Customer_Master.xlsx
- S4_BP_Target_Template.xlsx
- ECC_to_S4_Mapping.xlsx
- Business_Rules.xlsx
- Migration_Guide.pdf

## Generated Output Files

- S4_Customer_Cleaned.xlsx
- Rejected_Records.xlsx
- Migration_Issues.xlsx
- Approved_Field_Mappings.xlsx
- Transformation_Log.xlsx
- Migration_Summary.pdf

## Out of Scope

- Direct connection to a production SAP system
- Direct loading into SAP S/4HANA
- Material, vendor or finance migration
- Automatic deletion or duplicate merging
- Real client data
- Mobile application
- Kubernetes deployment

## Assumptions

- Synthetic data will be used.
- High-risk AI suggestions require human approval.
- The application will not directly modify SAP.
# Non-Functional Requirements

## Performance

- The MVP shall support at least 10,000 customer records.
- Normal pages should load within three seconds.
- Long-running assessments shall show progress.

## Security

- Production traffic shall use HTTPS.
- Passwords shall be securely hashed.
- API keys shall be stored outside source code.
- Users shall access only authorized projects.
- Uploaded files shall be validated by type and size.
- AI-generated SQL shall use a read-only database account.
- Sensitive data shall not appear in logs.

## Reliability

- Original source files shall never be modified.
- Failed jobs shall record an error status.
- Failed AI calls shall not corrupt migration data.
- Assessments shall support retry.

## Data Integrity

- Every modified value shall retain its original value.
- Every transformation shall record its reason and approver.
- Output files shall contain only approved changes.
- Dashboard calculations shall come from the database, not the LLM.

## AI Governance

- AI outputs shall be treated as recommendations.
- High-risk suggestions shall require manual approval.
- AI answers shall mention when evidence is unavailable.
- RAG answers shall include document references.
- AI shall never directly delete or modify records through chat.

## Maintainability

- Backend services shall be modular.
- Validation logic shall remain separate from API routes.
- Database changes shall use migrations.
- Environment settings shall use configuration files or environment variables.

## Testing

- Validation rules shall have unit tests.
- API endpoints shall have integration tests.
- Duplicate detection shall use a fixed evaluation dataset.
- CI/CD shall fail when mandatory tests fail.

## Deployment

- The project shall run locally using Docker Compose.
- The application shall be deployable to AWS or Azure.
- Production logs and health endpoints shall be available.
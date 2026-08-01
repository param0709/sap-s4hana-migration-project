import type { EccSchemaReference } from "../types";

interface SchemaLedgerProps {
  reference: EccSchemaReference;
  detectedColumns: string[];
}

interface LedgerRowProps {
  name: string;
  description: string;
  present: boolean;
  required: boolean;
}

function LedgerRow({ name, description, present, required }: LedgerRowProps) {
  const state = present ? "present" : required ? "missing" : "absent";
  const mark = present ? "\u2713" : required ? "\u2715" : "\u00B7";

  return (
    <div className={`ledger__row ledger__row--${state}`}>
      <span className={`ledger__mark ledger__mark--${state}`} aria-hidden="true">
        {mark}
      </span>
      <span className="ledger__field">{name}</span>
      <span className="ledger__note" title={description}>
        {description}
      </span>
      <span className="visually-hidden">
        {present ? "present in file" : required ? "required but missing" : "not supplied"}
      </span>
    </div>
  );
}

/**
 * Field-by-field readout of the ECC Customer Master layout against the upload.
 * Every expected field is listed whether or not it appeared, so the consultant
 * can see the gap rather than infer it.
 */
export function SchemaLedger({ reference, detectedColumns }: SchemaLedgerProps) {
  const present = new Set(detectedColumns);
  const known = new Set([
    ...reference.required_columns.map((column) => column.name),
    ...reference.optional_columns.map((column) => column.name),
  ]);
  const extra = detectedColumns.filter((column) => !known.has(column));

  return (
    <div className="ledger">
      <div className="ledger__group">
        <p className="ledger__caption">Required fields</p>
        <div className="ledger__rows">
          {reference.required_columns.map((column) => (
            <LedgerRow
              key={column.name}
              name={column.name}
              description={column.description}
              present={present.has(column.name)}
              required
            />
          ))}
        </div>
      </div>

      <div className="ledger__group">
        <p className="ledger__caption">Optional fields</p>
        <div className="ledger__rows">
          {reference.optional_columns.map((column) => (
            <LedgerRow
              key={column.name}
              name={column.name}
              description={column.description}
              present={present.has(column.name)}
              required={false}
            />
          ))}
        </div>
      </div>

      {extra.length > 0 ? (
        <div className="ledger__group">
          <p className="ledger__caption">Not in the ECC layout</p>
          <div className="chip-list">
            {extra.map((column) => (
              <span key={column} className="code-chip">
                {column}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

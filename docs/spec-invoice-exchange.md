# Spec Delta

## Purpose

Определяет двусторонний обмен счетами на оплату покупателю между порталом и бухгалтерскими контурами РФ и Казахстана через топики `invoices` и `invoices.exchange` на тех же механизмах, что и обмен контрагентами.

## ADDED Requirements

### Requirement: Supported invoice events

A contour SHALL process `invoice.created` and `invoice.updated` from `invoices` with `sender` `corp` as a full invoice snapshot (upsert) of `Документ.СчетНаОплатуПокупателю`, and `invoice.soft_delete` as a deletion mark. It SHALL publish `invoice.created` with `sender` `1c-rf` / `1c-kz` for invoices created in 1C. Messages from a 1C sender SHALL be acknowledged without data changes.

**Definition of Done:** each scenario in RF and KZ dev bases with fixtures.

#### Scenario: Portal creates an invoice
- **WHEN** a valid `invoice.created` with `sender` `corp` arrives
- **THEN** the contour creates the invoice and publishes started and completed to `invoices.exchange`

#### Scenario: Own outbound invoice is read back
- **WHEN** an `invoice.created` with `sender` `1c-rf` or `1c-kz` is read from `invoices`
- **THEN** it is acknowledged and no invoice changes

### Requirement: Invoice routing by organization

An invoice SHALL be routed by `organization-id` using counterparty routing rules and applied by one contour only. A routed invoice whose body `organization` does not resolve in the contour SHALL fail with `REFERENCE_NOT_FOUND`. An invoice without the header SHALL NOT be applied; each contour SHALL publish its own failed with `REQUIRED_HEADER_MISSING` for `organization-id`.

**Definition of Done:** fixtures with and without the header in both contours; statuses in `invoices.exchange`.

#### Scenario: Invoice routed to RF by header
- **WHEN** an invoice with `organization-id` `1` arrives
- **THEN** RF applies it and KZ records a filtering stage with no status

#### Scenario: Invoice without header
- **WHEN** an invoice arrives without `organization-id`
- **THEN** no invoice is created or changed, and RF and KZ each publish failed with `REQUIRED_HEADER_MISSING` for `organization-id`

### Requirement: Invoice Kafka key

Every portal message of one invoice, including `invoice.soft_delete`, SHALL carry Kafka key equal to the invoice `uid`. Outbound invoices SHALL use the same key. Ordering between messages of one invoice SHALL rely on that key.

**Definition of Done:** live portal invoice messages read via the Kafka UI API have key = body `uid`; a fixture pair in a dev base is applied in order.

#### Scenario: Soft delete follows an update
- **WHEN** `invoice.updated` waiting for its counterparty is followed by `invoice.soft_delete` with the same key
- **THEN** the soft delete is applied only after the update reaches a terminal state

### Requirement: Invoice body contract

Full snapshots SHALL carry `uid`, `number`, `released_at`, `sum`, `is_marked_delete` (boolean or 0/1), `contragent`, `organization`, `currency.rcc` (integer), `storehouse.uid` and `products[]`. Portal snapshots also require `id` and a selected `contract` with an id or uid. Bank account may be null.

**Definition of Done:** validate positive and negative fixtures in RF and KZ and compare with a portal invoice (PI-12).

#### Scenario: Product row fields
- **WHEN** a full invoice contains a product row
- **THEN** the row requires product uid, quantity, price, sum, sum_vat and nullable vat_percent; row id is ignored

#### Scenario: Row without product key
- **WHEN** an invoice row has no product `uid`
- **THEN** failed is published with `REQUIRED_FIELD_MISSING` for that row path and no invoice changes

#### Scenario: Contract missing on creation or update
- **WHEN** the portal creates or updates an invoice with `contract` absent, null, or empty, even if the customer has a default contract
- **THEN** the receiving contour immediately returns failed in `invoices.exchange` with `REQUIRED_FIELD_MISSING` at `contract`, without waiting for references and with no completed status, new document or changes to an existing document

#### Scenario: Compact deletion
- **WHEN** the portal sends a valid compact `invoice.soft_delete` without contract or responsible
- **THEN** the contour applies the existing deletion rules

### Requirement: Invoice reference resolution

The contour SHALL resolve customer and contract by their external keys, the chosen contract within the customer and organization, products by uid, organization by routing, warehouse and bank account by reference GUID, and currency by rcc. Unresolved references yield `REFERENCE_NOT_FOUND`, after the configured window for customer, specified contract or products.

**Definition of Done:** validate each reference and inspect the resulting invoice in both bases.

#### Scenario: Product of a row is unknown
- **WHEN** a row references a product unknown to the contour
- **THEN** after the waiting window failed is published with `REFERENCE_NOT_FOUND` for `products[i]` and no invoice is created or changed

#### Scenario: Multiple customer contracts
- **WHEN** two contracts exist and the portal supplies the key of the second valid contract
- **THEN** the receiving contour writes the specified contract, including when another contract is designated as the default

#### Scenario: A specified contract arrives later
- **WHEN** a valid contract reference for this customer and organization cannot yet be resolved
- **THEN** the normal retry window applies; resolution within the window allows completion, and an unresolved reference at expiry produces failed with `REFERENCE_NOT_FOUND` at `contract`

#### Scenario: Currency by numeric code
- **WHEN** an invoice arrives with `currency.rcc` `643`
- **THEN** the invoice currency is the currency with code `643`

#### Scenario: Warehouse without uid
- **WHEN** a KZ invoice arrives with `storehouse` `{id: 239, uid: null}` and the KZ contour has a default warehouse
- **THEN** the invoice is written with the default warehouse and completed is published; if there is no default it fails with `REQUIRED_FIELD_MISSING` at `storehouse.uid`

#### Scenario: Old RF counterparty without portal keys
- **WHEN** an RF invoice references a counterparty whose card has empty portal keys and reference GUID equal to `uid`
- **THEN** the invoice uses that card without waiting and completed is published

### Requirement: Portal manager as invoice responsible

RF and KZ SHALL set Ответственный from `responsible.uid` on portal invoice creation and update. An administrator maps one UID to one local user via «UID менеджера портала» on the user card.

**Definition of Done:** in both dev bases verify the field, unique mappings, create/update, terminal diagnostics and unchanged data on failure (PI-11).

#### Scenario: Manager reassignment
- **WHEN** a portal invoice previously assigned to manager A arrives with the mapped UID of manager B
- **THEN** the same invoice now references the local user for B

#### Scenario: Missing local mapping
- **WHEN** a well-formed manager UID has no corresponding user in the receiving base
- **THEN** the portal receives failed with `REFERENCE_NOT_FOUND` at `responsible.uid` and the invoice is not written

#### Scenario: No manager UID in a full snapshot (create or update)
- **WHEN** a portal create or update has no `responsible`, or `responsible.uid` is absent, null or blank
- **THEN** the receiving contour SHALL immediately publish failed in `invoices.exchange` with `REQUIRED_FIELD_MISSING` at `responsible.uid`, without creating or changing the invoice

#### Scenario: Ambiguous existing mapping
- **WHEN** the same incoming UID matches multiple existing users in the receiving base
- **THEN** the portal receives failed with `DUPLICATE_CONFLICT` at `responsible.uid` and the invoice is not written

#### Scenario: Same portal manager in two contours
- **WHEN** an administrator assigns a UID in RF and in KZ, and tries assigning it to a second user in the same base
- **THEN** the cross-base mappings are allowed and the local duplicate is rejected

### Requirement: Waiting for referenced counterparty and products

When `contragent`, `contract` or a row product is not found, the contour SHALL retry the invoice with growing delays within a configurable window (default 30 minutes). Started SHALL be published once. A waiting invoice SHALL delay only later messages with the same Kafka key. After the window failed SHALL carry `REFERENCE_NOT_FOUND` with the path.

**Definition of Done:** dev-base run with the invoice before its references; `invoices.exchange` read.

#### Scenario: Counterparty arrives later
- **WHEN** an invoice arrives before its new counterparty and the counterparty is applied 5 minutes later
- **THEN** the invoice is applied at the next retry and completed is published once

#### Scenario: Product never arrives
- **WHEN** a row product is still unknown when the waiting window ends
- **THEN** failed is published with `REFERENCE_NOT_FOUND` and the path of that row, e.g. `products[2].uid`

#### Scenario: Other invoices are not blocked
- **WHEN** an invoice waits for its counterparty and another invoice with a different key arrives in the same partition
- **THEN** the other invoice is applied without waiting

#### Scenario: Other reference is missing
- **WHEN** the `storehouse` of an invoice is not found
- **THEN** failed with `REFERENCE_NOT_FOUND` is published without waiting

### Requirement: Invoice soft delete event

`invoice.soft_delete` with `uid` and `id` SHALL find the invoice by invoice lookup and set the deletion mark by deletion rules. An unknown invoice SHALL be completed without changes. The legacy spelling `invoice_soft_delete` SHALL be accepted as the same event.

**Definition of Done:** fixtures for a known, an unknown and a closed-period invoice in RF and KZ; checked by a 1C query.

#### Scenario: Portal soft-deletes an invoice
- **WHEN** `invoice.soft_delete` arrives for a posted RF invoice in an open period
- **THEN** the invoice is marked for deletion, unposted, and completed is published

#### Scenario: Soft delete in a closed period
- **WHEN** `invoice.soft_delete` arrives for an invoice in a closed period
- **THEN** failed with `PERIOD_CLOSED` is published and the invoice does not change

#### Scenario: Soft delete of an unknown invoice
- **WHEN** `invoice.soft_delete` arrives for keys unknown to the contour
- **THEN** completed is published and no invoice is created

### Requirement: Deterministic invoice lookup

A contour SHALL find the invoice by `KFK_ВнешнийID` = `id`, then `KFK_ВнешнийUID` = `uid`, then the reference whose GUID equals `uid`. A found invoice SHALL get missing keys in the same transaction. A new invoice SHALL get `uid` as its reference GUID.

**Definition of Done:** each branch in a dev base; a 1C query shows no duplicate invoice.

#### Scenario: Portal updates an invoice created in 1C
- **WHEN** `invoice.updated` with `id` and the `uid` of an invoice created in 1C arrives
- **THEN** that invoice is updated and stores `KFK_ВнешнийID`

### Requirement: Invoice header mapping

A snapshot SHALL set date from `released_at`, `KFK_НомерПортала` from `number`, organization, counterparty, contract, mapped responsible user, warehouse, currency and bank account. The 1C document number SHALL NOT be taken from `number`. In KZ the bank account SHALL be a bank account of the organization, never a cash desk.

**Definition of Done:** RF and KZ fixtures; a 1C query shows the header values and an unchanged 1C number format.

#### Scenario: Portal number is stored separately
- **WHEN** an invoice with `number` `П-1024` is created
- **THEN** `KFK_НомерПортала` is `П-1024` and the 1C number follows the standard numbering

### Requirement: Invoice rows and VAT

Rows SHALL replace all invoice rows. VAT included SHALL be true when body `sum` equals the rows `sum` total and false when it equals rows `sum` + `sum_vat`; otherwise the invoice SHALL fail with `INVALID_FORMAT`. VAT rate SHALL come only from the row `vat_percent` via the contour table; null SHALL mean no VAT. In KZ service products SHALL go to TS `Услуги`.

**Definition of Done:** fixtures for included VAT, excluded VAT, inconsistent sums, null rate and a KZ service row; checked by a 1C query.

#### Scenario: Prices include VAT
- **WHEN** body `sum` equals the total of row `sum`
- **THEN** the invoice is written with VAT included and rates from the table

#### Scenario: Sums are inconsistent
- **WHEN** body `sum` equals neither total
- **THEN** failed is published with `INVALID_FORMAT` for `sum` and the invoice does not change

#### Scenario: Unmapped VAT percent
- **WHEN** a row has a `vat_percent` absent from the contour table
- **THEN** failed is published with `REFERENCE_NOT_FOUND` for that row `vat_percent`

#### Scenario: Null rate is not derived
- **WHEN** a row has `vat_percent` null and the product has VAT kind `Общая`
- **THEN** the row is written without VAT and 1C does not take the rate from the product or the organization

#### Scenario: Service row in KZ
- **WHEN** a KZ invoice row references a product marked as a service
- **THEN** the row is written to TS `Услуги` and not to `Товары`

### Requirement: Posting state on inbound invoice

Every RF invoice written from a portal message without a deletion mark SHALL be posted: a new invoice, an updated one and one whose deletion mark is cleared (customer answer: documents are posted immediately; decision 19.11.2026). In KZ the document SHALL only be written. A failed posting SHALL roll back the snapshot.

**Definition of Done:** RF invoices updated and unmarked; a KZ invoice created and updated; posting state checked by a 1C query.

#### Scenario: Posted RF invoice is updated
- **WHEN** an update arrives for a posted RF invoice in an open period
- **THEN** the invoice is rewritten and stays posted

#### Scenario: Deletion mark cleared on an RF invoice
- **WHEN** `is_marked_delete` false arrives for an RF invoice that the portal marked for deletion
- **THEN** the mark is cleared and the invoice is posted again

#### Scenario: Posting fails
- **WHEN** reposting the updated invoice fails
- **THEN** failed is published and the invoice keeps its previous content

### Requirement: Closed period protection

If the stored or incoming date is in a closed period, the contour SHALL reject the write, including deletion marking, with `PERIOD_CLOSED` and preserve the invoice. This applies to full-rights exchange users, regardless of the KZ full-rights option.

**Definition of Done:** a prohibition date is set in RF and KZ dev bases; update and deletion fixtures give `PERIOD_CLOSED` and an unchanged document.

#### Scenario: Update in a closed period
- **WHEN** an update arrives for an invoice dated before the prohibition date
- **THEN** failed with `PERIOD_CLOSED` is published and the invoice does not change

#### Scenario: Full-rights exchange user in KZ
- **WHEN** the KZ exchange runs under a full-rights user, the full-rights option is off, and an update arrives for an invoice in a closed period
- **THEN** failed with `PERIOD_CLOSED` is published and the invoice does not change

#### Scenario: Date moved into a closed period
- **WHEN** an update moves an open-period invoice to a date before the prohibition date
- **THEN** failed with `PERIOD_CLOSED` is published and the invoice does not change

### Requirement: Deletion mark from portal

`is_marked_delete` true SHALL set the deletion mark (an RF posted invoice becomes unposted); false SHALL clear it. A new invoice arriving with `is_marked_delete` true SHALL NOT be created and SHALL be completed without `accounting_number`.

**Definition of Done:** fixtures for marking, unmarking and an unknown marked invoice; checked by a 1C query.

#### Scenario: Portal deletes an invoice
- **WHEN** an update with `is_marked_delete` true arrives for a posted RF invoice in an open period
- **THEN** the invoice is marked for deletion and unposted

#### Scenario: Unknown invoice arrives deleted
- **WHEN** an `invoice.created` with `is_marked_delete` true and unknown keys arrives
- **THEN** no invoice is created and completed is published without `accounting_number`

### Requirement: Invoice status exchange

A contour SHALL publish `invoice.exchange_started`, `_completed` and `_failed` to `invoices.exchange` as for counterparties. Completed SHALL carry `accounting_number`, the 1C document number. The contour SHALL read `corp` statuses from `invoices.exchange` for its outbound invoice records with counterparty filtering rules.

**Definition of Done:** statuses of both directions read from `invoices.exchange`; record state checked by a 1C query.

#### Scenario: Completed carries the 1C number
- **WHEN** an inbound invoice is applied
- **THEN** the completed status contains `accounting_number` equal to the document number in 1C

#### Scenario: Portal rejects an outbound invoice
- **WHEN** `invoice.exchange_failed` with `sender` `corp` and a matching `causation-id` arrives
- **THEN** the outbound invoice record becomes failed and stores `messages[]`

### Requirement: Outbound invoice on first write

Each contour SHALL register one `invoice.created` per new invoice at its first write after enablement, in RF and KZ alike. Invoices created by the exchange, written with `ОбменДанными.Загрузка`, marked for deletion, older invoices and later edits SHALL NOT be registered. `uid` SHALL equal the reference GUID and be stored in the creating transaction.

**Definition of Done:** RF and KZ scenarios; outbound record count and stored uid checked by a 1C query.

#### Scenario: User saves a draft invoice
- **WHEN** a user saves a new invoice in KZ
- **THEN** exactly one outbound record is registered

#### Scenario: User posts the invoice later
- **WHEN** an RF invoice that already has an outbound record is posted
- **THEN** no second record is registered

### Requirement: Outbound invoice dependencies

The publisher SHALL send an invoice only when the portal has completed every referenced counterparty and product that has an outbound record. A pending or sent dependency SHALL postpone the invoice; a failed one SHALL fail it with `DEPENDENCY_FAILED` and the object path. An object without an outbound record SHALL be referenced by its stored keys or reference GUID.

**Definition of Done:** each dependency state reproduced in a dev base; 1C query and topic.

#### Scenario: Product not sent yet
- **WHEN** an invoice references a product whose outbound record is pending
- **THEN** the invoice record stays pending

#### Scenario: Portal has not confirmed the counterparty
- **WHEN** the counterparty outbound record of the invoice is sent but the portal has not completed it
- **THEN** the invoice record stays pending and is published only after the portal completes the counterparty

#### Scenario: All dependencies completed
- **WHEN** the portal has completed the counterparty and every new product of the invoice
- **THEN** the invoice is published at the next publisher run

#### Scenario: Counterparty rejected by portal
- **WHEN** the counterparty outbound record of the invoice is failed
- **THEN** the invoice record becomes failed with `DEPENDENCY_FAILED` for `contragent`

### Requirement: Outbound invoice message contract

An outbound invoice SHALL go to `invoices` with `sender` `1c-rf` / `1c-kz`, new UUID `id` and `correlation-id`, `type` `invoice.created` (legacy `invoice_created` until switched), `version` `1.0.0`, `organization-id` of the document organization, key = `uid`. The body SHALL follow schema `1.0.0` without `id`, with `number` the 1C number and all goods and service rows, each by product `uid`.

**Definition of Done:** RF and KZ records in the Kafka UI API; body valid against `1.0.0`.

#### Scenario: KZ invoice with services
- **WHEN** a KZ invoice with goods and service rows is published
- **THEN** `products[]` contains every goods and service row

#### Scenario: Organization has no portal id
- **WHEN** the invoice organization has no portal id
- **THEN** nothing is published and the record becomes failed with `organization` in its diagnostics

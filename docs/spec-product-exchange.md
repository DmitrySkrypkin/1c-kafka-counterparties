# Spec Delta

## Purpose

Определяет двусторонний обмен номенклатурой между порталом и бухгалтерскими контурами РФ и Казахстана через топики `products` и `products.exchange` на тех же механизмах, что и обмен контрагентами.

## ADDED Requirements

### Requirement: Supported product events

A contour SHALL process `product.created` and `product.updated` from `products` with `sender` `corp` as a full product snapshot (upsert). It SHALL publish `product.created` with `sender` `1c-rf` / `1c-kz` for products created in 1C. Messages from a 1C sender SHALL be acknowledged without data changes. Legacy `_` spellings SHALL be accepted (*Event type naming transition*).

**Definition of Done:** each scenario in RF and KZ dev bases with fixtures and one live portal message.

#### Scenario: Portal sends product.updated
- **WHEN** a valid `product.updated` with `sender` `corp` arrives in `products`
- **THEN** the contour applies it as a full snapshot and publishes started and completed to `products.exchange`

#### Scenario: Own outbound message is read back
- **WHEN** the contour reads a `product.created` with `sender` `1c-rf` or `1c-kz` from `products`
- **THEN** it is acknowledged, no product changes, and a filtering stage is recorded

### Requirement: Product envelope and routing

A product message SHALL carry headers `id`, `correlation-id`, `type`, `version`, `sender`, `timestamp-ms` (10 digits in seconds or 13 in milliseconds) and key equal to the product `uid`. Every contour SHALL process every product message; `organization-id` SHALL NOT be required for products.

**Definition of Done:** one fixture processed in RF and KZ; both outcomes read from `products.exchange`.

#### Scenario: Broadcast product
- **WHEN** a portal product message without `organization-id` arrives
- **THEN** RF and KZ each apply it and each publish their own completed status

#### Scenario: Timestamp in milliseconds
- **WHEN** a portal product message carries a thirteen-digit `timestamp-ms`
- **THEN** the envelope check passes

#### Scenario: Envelope is malformed
- **WHEN** a product message has no `id` header or an unparsable body
- **THEN** it is quarantined, no product changes, and the consumer continues with the next offset

### Requirement: Product body contract

Inbound body schema `1.0.0` SHALL require `uid` (string 36) and `name` (non-empty string). `id` SHALL be optional and SHALL NOT be used by 1C. `article`, `weight`, `country` (`{id, oksm}`), `unit` (`{okei}`: 3-digit string) and `is_service` (boolean, default false) SHALL be optional and nullable. Unknown fields, including `vat_percent`, SHALL be ignored.

**Definition of Done:** valid and invalid fixtures for each field pass or fail schema `1.0.0` with the expected code.

#### Scenario: Portal body without id
- **WHEN** a `corp` product body has `uid` and `name` and no `id`
- **THEN** it passes validation and is applied

#### Scenario: Body without uid
- **WHEN** a product body has no `uid`
- **THEN** failed is published with `REQUIRED_FIELD_MISSING` for `uid` and no product changes

#### Scenario: Empty name
- **WHEN** a product body has an empty `name`
- **THEN** failed is published with a validation error for `name`

### Requirement: Product lookup by uid only

A contour SHALL find the product by `KFK_ВнешнийUID` = `uid`, then by the reference whose GUID equals `uid`. Groups SHALL NOT match. The portal `id` SHALL NOT be stored or used for lookup. When `uid` matches one product in the attribute and another by reference, the message SHALL fail with `DUPLICATE_CONFLICT` without changes.

**Definition of Done:** each branch reproduced in RF and KZ dev bases; a 1C query shows no duplicate product.

#### Scenario: New or RF product found by reference
- **WHEN** a snapshot arrives whose `uid` equals the reference GUID of an existing product
- **THEN** that product is updated and no other product is created

#### Scenario: Linked KZ product found by attribute
- **WHEN** a snapshot arrives in KZ whose `uid` is stored in `KFK_ВнешнийUID` of an old product with a different reference GUID
- **THEN** that product is updated and no other product is created

#### Scenario: uid points to two products
- **WHEN** `uid` is held in `KFK_ВнешнийUID` by one product and equals the reference GUID of another
- **THEN** failed is published with `DUPLICATE_CONFLICT` and neither product changes

### Requirement: One-time linking of existing KZ products

Before product inbound is enabled in KZ, every existing KZ product that the old file exchange received from the portal SHALL hold the portal `uid` in `KFK_ВнешнийUID`. Products that cannot be matched SHALL be reported in a list for manual review and SHALL NOT be changed.

**Definition of Done:** after the linking run, a 1C query counts linked products of the portal folder; a sample of 20 is checked against live `products` messages; the unmatched list is handed over.

#### Scenario: Old KZ product is linked
- **WHEN** the linking run processes a KZ product received by the old exchange as portal product `153497`
- **THEN** its `KFK_ВнешнийUID` equals the portal `uid` of that product and its reference is unchanged

#### Scenario: Product cannot be matched
- **WHEN** a KZ product of the portal folder has no matching portal `uid`
- **THEN** it is listed for manual review and not changed

### Requirement: New product from portal

When no product matches, a contour SHALL create an item with `uid` as its reference GUID, in the portal product folder and with kind, unit and VAT defaults configured for the contour. A contour without configured defaults SHALL fail the message with a configuration error.

**Definition of Done:** a new product created in RF and KZ has the configured folder, kind, unit and VAT; its GUID equals `uid`; checked by a 1C query.

#### Scenario: Unknown product arrives
- **WHEN** a snapshot with an unknown `uid` arrives and defaults are configured
- **THEN** a new item with GUID `uid` is created in the configured folder with the default kind, unit and VAT

#### Scenario: Same product in both contours
- **WHEN** a snapshot for a new product is applied by RF and KZ
- **THEN** both contours hold the product with the same reference GUID equal to `uid`

#### Scenario: Defaults are missing
- **WHEN** a snapshot for an unknown product arrives and the contour has no default folder
- **THEN** failed is published with a configuration error and no item is created

### Requirement: Optional product attributes on creation

On creation, `unit.okei` SHALL find the unit by code or add it from the built-in OKEI classifier, and `is_service` SHALL set the service flag; a missing field SHALL take the default. The VAT kind SHALL always come from the contour default; product `vat_percent` SHALL NOT be used. These fields SHALL NOT change an existing product. A code absent from OKEI SHALL fail with `REFERENCE_NOT_FOUND` for `unit.okei`.

**Definition of Done:** RF and KZ fixtures with and without each field; 1C query.

#### Scenario: Portal sends unit
- **WHEN** a new product arrives with `unit.okei` `796` in RF
- **THEN** it is created with unit code `796` and the default VAT kind

#### Scenario: Portal still sends product VAT
- **WHEN** a new product arrives with `vat_percent` `10`
- **THEN** the field is ignored and the product gets the default VAT kind

#### Scenario: Fields are absent
- **WHEN** a new product arrives without `unit` and `is_service`
- **THEN** it is created with the contour defaults

#### Scenario: Existing product gets another unit
- **WHEN** a snapshot with a different `unit.okei` arrives for an existing product
- **THEN** the product unit does not change

#### Scenario: Unit is added from OKEI
- **WHEN** a new product arrives with `unit.okei` `"006"` and the base has no unit with code `006`
- **THEN** the unit `м` is added from the built-in OKEI classifier and set on the product

#### Scenario: Unknown unit code
- **WHEN** a new product arrives with a `unit.okei` absent from the built-in OKEI classifier
- **THEN** failed is published with `REFERENCE_NOT_FOUND` for `unit.okei` and no product is created

### Requirement: Product field mapping

A snapshot SHALL set `Наименование` and `НаименованиеПолное` from `name`, `Артикул` from `article`, weight from `weight`, and in RF `СтранаПроисхождения` by `country.oksm`. A null field SHALL clear the attribute. KZ SHALL ignore `country`. Kind, unit, folder and VAT of an existing product SHALL NOT change.

**Definition of Done:** RF and KZ fixtures with filled and null fields; a 1C query shows the mapped values.

#### Scenario: Article becomes null
- **WHEN** a snapshot with `article` null arrives for a product with an article
- **THEN** the product article becomes empty

#### Scenario: Country in KZ
- **WHEN** a snapshot with `country` arrives in KZ
- **THEN** the product is applied and no country is written

#### Scenario: Unknown country code in RF
- **WHEN** `country.oksm` has no matching country in RF
- **THEN** failed is published with `REFERENCE_NOT_FOUND` for `country` and the product does not change

### Requirement: Outbound product snapshot on creation

Each contour SHALL publish one `product.created` per new non-group product created after enablement. Items created by the exchange, written with `ОбменДанными.Загрузка`, groups, older items and later edits SHALL NOT be published. The item `uid` SHALL equal its reference GUID and be stored in `KFK_ВнешнийUID` in the creating transaction.

**Definition of Done:** RF and KZ scenarios; outbound record count and stored uid checked by a 1C query.

#### Scenario: User creates a product
- **WHEN** a user saves a new product item in RF
- **THEN** exactly one outbound record is registered and `KFK_ВнешнийUID` equals the reference GUID

#### Scenario: User creates a group
- **WHEN** a user saves a new product group
- **THEN** no outbound record is registered

#### Scenario: Product is edited later
- **WHEN** a product that already has an outbound record is written again
- **THEN** no second record is registered

### Requirement: Outbound product message contract

An outbound product SHALL go to `products` with `sender` `1c-rf` / `1c-kz`, new UUID `id` and `correlation-id`, `type` `product.created` (legacy `product_created` until switched), `version` `1.0.0`, no `organization-id`, key = `uid`. The body SHALL carry `uid`, `name`, `article`, `weight`, `country` (`{oksm}` in RF, null in KZ), `unit{okei}`, `is_service`, without `id` and without VAT.

**Definition of Done:** RF and KZ records in the Kafka UI API; body valid against `1.0.0`.

#### Scenario: RF publishes a product
- **WHEN** the RF publisher sends a registered product
- **THEN** the record has `sender` `1c-rf`, key equal to `uid`, and a valid body with the country OKSM code

#### Scenario: KZ publishes a product
- **WHEN** the KZ publisher sends a registered product
- **THEN** the record has `sender` `1c-kz` and `country` null

### Requirement: Product status exchange

A contour SHALL publish started, completed and failed for inbound product messages to `products.exchange` as for counterparties, with types `product.exchange_*`. It SHALL read `corp` statuses from `products.exchange` and update its outbound product records by `causation-id`, else `correlation-id`, with the same filtering rules as counterparty status consumption.

**Definition of Done:** statuses of both directions read from `products.exchange`; record state checked by a 1C query.

#### Scenario: Portal completes an outbound product
- **WHEN** `product.exchange_completed` with `sender` `corp` and a matching `causation-id` arrives
- **THEN** the outbound product record becomes completed

#### Scenario: Product created in RF reaches KZ
- **WHEN** the portal broadcasts a `product.updated` for a product created in RF 1C
- **THEN** RF updates its product without a duplicate and KZ creates the product with the same reference GUID

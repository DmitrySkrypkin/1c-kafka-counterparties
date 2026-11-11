# Delta for counterparty-exchange

## MODIFIED Requirements

### Requirement: Supported counterparty events

The exchange SHALL consume `contragent_created` and `contragent_updated` events from `contragents`. Each event SHALL represent a full current snapshot of one counterparty. Processing statuses SHALL be published to `contragents.exchange`. The message type SHALL NOT decide between creating and updating a card; the deterministic lookup SHALL decide.

**Definition of Done:** fixtures of both types are applied in RF and KZ dev bases; an `updated` with no matching card creates exactly one card, verified by a 1C query.

#### Scenario: Create event is accepted
- **WHEN** a routed message has type `contragent_created`
- **THEN** the target contour processes it as a complete new counterparty snapshot

#### Scenario: Update event is accepted
- **WHEN** a routed message has type `contragent_updated`
- **THEN** the target contour processes it as a complete replacement snapshot of the existing counterparty

#### Scenario: Update event has no matching card
- **WHEN** a routed `contragent_updated` matches no card by `id`, `uid`, or registration data and passes the contour validation
- **THEN** the contour creates one card from the snapshot and publishes completed

### Requirement: Input envelope contract

Every input message MUST contain `sender`, `correlation-id`, `timestamp-ms`, `id`, `type`, and `version` headers. `organization-id` SHALL be optional. Message `id` MUST be a UUID, `timestamp-ms` MUST be Unix time in seconds (exactly 10 digits; header name kept as in TZ), and only configured schema versions SHALL be accepted. A contour SHALL apply only messages whose `sender` is `corp`.

**Definition of Done:** envelope fixtures for each scenario give the stated outcome; a message published by `1c-rf` or `1c-kz` to `contragents` changes no data and produces no status, verified through the stage journal and the topic.

#### Scenario: Valid envelope arrives
- **WHEN** all required headers have valid values and the version is supported
- **THEN** the message is eligible for contour routing

#### Scenario: Required header is missing
- **WHEN** a required header other than `organization-id` is missing
- **THEN** no business data is changed and the message fails with `REQUIRED_FIELD_MISSING` when a correlated response can be formed

#### Scenario: Timestamp uses seconds as in TZ
- **WHEN** `timestamp-ms` contains a ten-digit Unix timestamp in seconds
- **THEN** the envelope timestamp check passes

#### Scenario: Timestamp uses milliseconds
- **WHEN** `timestamp-ms` contains a thirteen-digit Unix timestamp in milliseconds
- **THEN** no business data is changed and the message fails with `INVALID_FORMAT`

#### Scenario: Major version is unsupported
- **WHEN** the message major version is not configured as supported
- **THEN** no business data is changed and the message fails with `UNSUPPORTED_VERSION`

#### Scenario: Message was published by a 1C contour
- **WHEN** a message in `contragents` has `sender` `1c-rf`, `1c-kz`, or any value other than `corp`
- **THEN** every contour acknowledges it without business processing, without a status, and records a filtering stage

### Requirement: Core counterparty body

The body MUST contain non-blank `name`. A body from `sender` `corp` MUST contain numeric `id`. A body published by a 1C contour MUST contain `uid` and MAY omit `id`. Optional nullable fields SHALL include `uid`, `kpp`, `ogrn`, `name_short`, `is_provider`, `is_client`, `is_transporter`, `is_other_relationship`, `is_separate`, `type_entity`, `reg_number`, `head_contragent`, `additional_information`, and `country`. A supplied `uid` MUST be a UUID.

**Definition of Done:** schema `1.1.0` fixtures — minimum portal body, minimum 1C body, portal body without `id`, 1C body without `uid`, blank name, invalid uid — give the stated outcomes in the contour validator and in the JSON Schema check.

#### Scenario: Minimum valid body is received
- **WHEN** the body contains valid `id` and `name` and omits all optional fields and collections
- **THEN** it passes required-field validation and omitted collections are treated as empty

#### Scenario: Portal body lacks numeric id
- **WHEN** a body with `sender` `corp` has no valid numeric `id`
- **THEN** the message fails with `REQUIRED_FIELD_MISSING` at path `id`

#### Scenario: 1C body carries uid without id
- **WHEN** a body published by a 1C contour contains valid `uid` and `name` and no `id`
- **THEN** it conforms to schema `1.1.0`

#### Scenario: Name is blank
- **WHEN** `name` is absent, null, empty, or whitespace-only
- **THEN** the message fails with `REQUIRED_FIELD_MISSING` at path `name`

#### Scenario: UID has invalid syntax
- **WHEN** optional `uid` is present but is not a UUID
- **THEN** the message fails with `INVALID_FORMAT` at path `uid`

### Requirement: Bank account snapshot

Every `bank_accounts` item MUST have at least one stable external key in numeric `id` or UUID `uid`, and SHALL support optional nullable `number`, `bic`, `name`, and `is_default`. The collection SHALL be the complete set for the counterparty. The adapter SHALL find an existing account by `id` first and then by `uid`, and SHALL link a key that the found account does not hold yet. The exchange SHALL preserve each supplied `is_default` value subject to target-system recording rules.

**Definition of Done:** in RF and KZ an account first stored with only `uid` is found by that `uid` from a portal snapshot carrying `id`+`uid`, receives the `id`, and is not marked for deletion; verified by a 1C query on `KFK_ВнешнийID`, `KFK_ВнешнийUID`, and `ПометкаУдаления`.

#### Scenario: Bank account lacks identity
- **WHEN** a bank account item has neither a valid `id` nor a valid `uid`
- **THEN** validation adds `REQUIRED_FIELD_MISSING` at that item path

#### Scenario: Bank account is matched by uid
- **WHEN** a snapshot item carries `id` and `uid`, no account holds that `id`, and one account of the owner holds that `uid`
- **THEN** that account is updated, receives the `id`, and stays unmarked for deletion

#### Scenario: Account keys point to different accounts
- **WHEN** the item `id` and `uid` resolve to two different accounts
- **THEN** no data is changed and failed contains `DUPLICATE_CONFLICT` at that item path

#### Scenario: Default flag is supplied
- **WHEN** a bank account contains a valid `is_default` value
- **THEN** the adapter passes that value to the contour mapping without inventing an additional contract restriction

### Requirement: Deterministic counterparty lookup

The adapter SHALL search by external `id` and by optional `uid` first. The external identifiers MUST resolve to no more than one consistent counterparty. Registration data (`reg_number + kpp` in RF, `reg_number` in KZ) SHALL be used only as a fallback when neither `id` nor `uid` matches any card; duplicates by registration data SHALL NOT block a card already found by `id` or `uid`. A unique match SHALL be linked to every supplied external identifier it does not hold yet. When nothing matches, the adapter SHALL create a card.

**Definition of Done:** each scenario is reproduced in RF and KZ dev bases with fixtures; the card count and the stored `KFK_ВнешнийID` / `KFK_ВнешнийUID` are verified by a 1C query.

#### Scenario: External ID matches
- **WHEN** exactly one counterparty is linked to the supplied `id`
- **THEN** that counterparty is updated without creating another card

#### Scenario: Card created in 1C is matched by uid
- **WHEN** a portal snapshot carries `id` and `uid`, no card holds that `id`, and one card holds that `uid`
- **THEN** that card is updated, receives `KFK_ВнешнийID` equal to `id`, and no other card is created

#### Scenario: Registration data gives one fallback match
- **WHEN** neither `id` nor `uid` is linked and exactly one card matches `reg_number + kpp`
- **THEN** that card receives the external identifiers and is updated

#### Scenario: Nothing matches
- **WHEN** no card matches by `id`, `uid`, or registration data
- **THEN** one new card is created with the supplied external identifiers

#### Scenario: Card found by uid has registration duplicates
- **WHEN** one card holds the supplied `uid`, no card holds the supplied `id`, and several other cards share its `reg_number + kpp`
- **THEN** the card found by `uid` is updated and receives `KFK_ВнешнийID`, and the registration duplicates are neither checked nor changed

#### Scenario: Identifiers point to different cards
- **WHEN** the supplied `id` and `uid` resolve to different counterparties
- **THEN** no data is changed and failed contains `DUPLICATE_CONFLICT`

#### Scenario: External id belongs to another card
- **WHEN** the supplied `id` is already held by a different card than the one holding the supplied `uid`
- **THEN** no data is changed and failed contains `DUPLICATE_CONFLICT`

#### Scenario: Fallback has multiple matches
- **WHEN** neither `id` nor `uid` matches and more than one card matches the registration data
- **THEN** no card is selected and failed contains `DUPLICATE_CONFLICT`

## ADDED Requirements

### Requirement: Outbound snapshot on counterparty creation

Each contour SHALL publish one `contragent_created` snapshot per new `Справочник.Контрагенты` card created after enablement. Cards created by the portal exchange, writes with `ОбменДанными.Загрузка`, older cards, and later edits SHALL NOT be published.

**Definition of Done:** each scenario in RF and KZ dev bases; outbound record count checked by a 1C query.

#### Scenario: User creates a card
- **WHEN** a user saves a new counterparty card in RF
- **THEN** exactly one outbound snapshot is registered for that card

#### Scenario: Card is created by the portal exchange
- **WHEN** the inbound adapter creates a card from a portal snapshot
- **THEN** no outbound snapshot is registered

#### Scenario: Card is written in data-load mode
- **WHEN** a new card is written with `ОбменДанными.Загрузка = Истина`
- **THEN** no outbound snapshot is registered

#### Scenario: Card is edited after creation
- **WHEN** a card that already has an outbound snapshot is written again
- **THEN** no second outbound snapshot is registered and nothing is published

### Requirement: 1C-generated external identifiers

A new card SHALL get `uid` equal to its reference GUID, stored in `KFK_ВнешнийUID` in the creating transaction. Sent bank accounts and contracts SHALL carry their own reference GUID as `uid`, stored in their `KFK_ВнешнийUID`. An existing key SHALL NOT be overwritten.

**Definition of Done:** a 1C query shows stored uid equal to the reference GUID for the card and each sent child; rollback leaves no card and no outbound record.

#### Scenario: New card receives uid
- **WHEN** a new card is committed
- **THEN** its `KFK_ВнешнийUID` equals the 36-character GUID of its reference

#### Scenario: Card creation is rolled back
- **WHEN** the transaction that creates the card is rolled back
- **THEN** no card, no stored uid, and no outbound record remain

#### Scenario: Child already has a uid
- **WHEN** a bank account or contract included in the snapshot already holds `KFK_ВнешнийUID`
- **THEN** the snapshot sends that stored value unchanged

### Requirement: Outbound message contract

An outbound snapshot SHALL go to `contragents` with `sender` `1c-rf`/`1c-kz`, new UUID `id` and `correlation-id`, `timestamp-ms` in seconds, `type` `contragent_created`, `version` `1.1.0`, `organization-id` of the publishing contour, and Kafka key equal to the card `uid`. The body SHALL follow schema `1.1.0`.

**Definition of Done:** RF and KZ records read via the Kafka UI API show these headers and key; the body passes schema `1.1.0`.

#### Scenario: RF publishes a snapshot
- **WHEN** the RF publisher sends a registered snapshot
- **THEN** the record has `sender` `1c-rf`, `organization-id` `1`, key equal to the card `uid`, and a body valid against schema `1.1.0`

#### Scenario: KZ publishes a snapshot
- **WHEN** the KZ publisher sends a registered snapshot
- **THEN** the record has `sender` `1c-kz` and `organization-id` `5`

#### Scenario: Contract has no organization
- **WHEN** the snapshot contains a contract without an organization or with an organization that has no portal `id`
- **THEN** nothing is published, the record becomes failed with the contract path in its diagnostics, and an administrator resend after the contract is fixed publishes a fresh snapshot

### Requirement: Consumer read position

A contour consumer SHALL resume reading from the offset committed for its consumer group in Kafka. The 1C offset mirror SHALL NOT move the read position; a differing mirror SHALL be logged and updated to the committed offset.

**Definition of Done:** with the mirror below the committed offset, the started consumer reads the next message and the mirror is updated; checked by a 1C query.

#### Scenario: Mirror lags behind the group
- **WHEN** the 1C offset mirror is lower than the committed offset of the consumer group
- **THEN** the consumer starts reading at the committed offset, records a warning, and updates the mirror

### Requirement: Identity binding inside the snapshot transaction

Linking external identifiers to a card, or creating a card for a new snapshot, SHALL be part of the same transaction as applying the snapshot body. When the snapshot is not applied, the linked identifiers and the created card SHALL be rolled back before the failed status is published.

**Definition of Done:** a snapshot that fails during application is processed in a dev base; a 1C query shows no new card and no changed `KFK_ВнешнийID`.

#### Scenario: New card snapshot fails during application
- **WHEN** a snapshot for an unknown counterparty fails with `REFERENCE_NOT_FOUND` while its body is applied
- **THEN** failed is published and no card with its `id` or `uid` exists

#### Scenario: Existing card snapshot fails during application
- **WHEN** a snapshot matched to an existing card by `uid` fails while its body is applied
- **THEN** failed is published and the card keeps its previous `KFK_ВнешнийID`

### Requirement: Transactional outbound outbox

The outbound record SHALL be created in the card-creation transaction. A background publisher SHALL send it after a configured delay, building the body at send time. A record SHALL succeed at most once, keep its message `id` across retries, and stay pending while Kafka is unavailable.

**Definition of Done:** Kafka outage and the delay window are reproduced in a dev base; checked by a 1C query and the topic.

#### Scenario: Child is added within the delay
- **WHEN** a bank account is added to the new card before the publication delay expires
- **THEN** the published snapshot contains that account with its `uid`

#### Scenario: Child is added after the snapshot was sent
- **WHEN** a bank account is added to the card after its snapshot was published
- **THEN** that account is not in the published message, and a later full portal snapshot without it marks it for deletion as for any account missing from a full snapshot

#### Scenario: Kafka is unavailable
- **WHEN** the publisher cannot reach Kafka
- **THEN** the record stays pending with a transport error and is retried with the same message `id`

#### Scenario: Delivery succeeds
- **WHEN** Kafka acknowledges the record
- **THEN** the record becomes sent and is never published again

### Requirement: Portal status consumption

Each contour SHALL read `contragents.exchange` with its own consumer group and accept only `sender` `corp` statuses whose `correlation-id` matches its outbound record. Started, completed, and failed SHALL update that record; failed SHALL keep `messages[]`. Any other message SHALL be acknowledged without data changes and MUST NOT stop the consumer.

**Definition of Done:** each scenario is read from `contragents.exchange` by the running consumer; record state is checked by a 1C query in RF and KZ.

#### Scenario: Portal completes a snapshot
- **WHEN** a `contragent_exchange_completed` with `sender` `corp` and a matching `correlation-id` arrives
- **THEN** the outbound record becomes completed

#### Scenario: Portal rejects a snapshot
- **WHEN** a `contragent_exchange_failed` with `sender` `corp` and a matching `correlation-id` arrives
- **THEN** the outbound record becomes failed and stores the received `messages[]`

#### Scenario: Status belongs to a 1C contour
- **WHEN** a status with `sender` `1c-rf` or `1c-kz` arrives
- **THEN** it is acknowledged and no outbound record changes

#### Scenario: Correlation is unknown
- **WHEN** a `corp` status carries a `correlation-id` with no outbound record in this contour
- **THEN** it is acknowledged, no record changes, and a filtering stage is recorded

#### Scenario: Status message has no headers
- **WHEN** a message without headers or without a message `id` arrives in `contragents.exchange`
- **THEN** it is acknowledged, no record changes, and the consumer continues with the next offset

#### Scenario: Late status after a terminal one
- **WHEN** a `corp` started status arrives for a record that is already completed
- **THEN** it is acknowledged, the record stays completed, and a filtering stage is recorded

### Requirement: Explicit resend of a failed outbound snapshot

A failed or undelivered outbound record SHALL be resent only by an explicit administrator command for that record. A resend SHALL build a fresh body and publish it with a new message `id` and a new `correlation-id`, keeping the link to the original record.

**Definition of Done:** the administrator command on one failed record publishes one new message with new identifiers; other records and the card are unchanged; verified by a 1C query and the topic.

#### Scenario: Administrator resends a failed snapshot
- **WHEN** the administrator runs the resend command on a failed outbound record
- **THEN** one new snapshot with new message `id` and `correlation-id` is published for that card

#### Scenario: No automatic resend after failure
- **WHEN** an outbound record is failed and no command is run
- **THEN** nothing is published again for that card

### Requirement: Contract version coexistence

Contract schemas `1.0.0` and `1.1.0` SHALL be kept side by side. Contours SHALL accept inbound versions `1.0.*` and `1.1.*`. Version `1.1.0` SHALL differ from `1.0.0` only in the optional body `id` for a 1C sender, the required body `uid` for a 1C sender, and the bank account key `id` or `uid`.

**Definition of Done:** all existing `1.0.0` valid and invalid fixtures keep their outcome; `1.1.0` fixtures cover each difference with a valid and an invalid case.

#### Scenario: Portal still sends version 1.0
- **WHEN** a portal snapshot with version `1.0.0` arrives
- **THEN** it is processed exactly as before this change

#### Scenario: Portal sends a bank account with uid only
- **WHEN** a portal snapshot with version `1.1.0` carries a bank account with `uid` and no `id`
- **THEN** the account passes validation and is matched by `uid`

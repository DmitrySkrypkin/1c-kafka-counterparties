# counterparty-exchange Specification

## Purpose

Определяет единый проверяемый контракт доставки полного снимка контрагента из портала в бухгалтерские контуры РФ и Казахстана через Kafka и публикации результата обработки.

## Requirements

### Requirement: Supported counterparty events

The exchange SHALL consume `contragent_created` and `contragent_updated` events from `contragents`. Each event SHALL represent a full current snapshot of one counterparty. Processing statuses SHALL be published to `contragents.exchange`.

#### Scenario: Create event is accepted
- **WHEN** a routed message has type `contragent_created`
- **THEN** the target contour processes it as a complete new counterparty snapshot

#### Scenario: Update event is accepted
- **WHEN** a routed message has type `contragent_updated`
- **THEN** the target contour processes it as a complete replacement snapshot of the existing counterparty

### Requirement: Input envelope contract

Every input message MUST contain `sender`, `correlation-id`, `timestamp-ms`, `id`, `type`, and `version` headers. `organization-id` SHALL be optional. Message `id` MUST be a UUID, `timestamp-ms` MUST be Unix time in seconds (exactly 10 digits; header name kept as in TZ), and only configured major schema versions SHALL be accepted.

#### Scenario: Valid envelope arrives
- **WHEN** all required headers have valid values and the major version is supported
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

### Requirement: Contour routing

Contour codes SHALL be configurable, with initial values `1` for RF and `5` for KZ. A contour MUST process its own code, both contours MUST process a message without `organization-id`, and a contour MUST silently skip any other code without publishing a status.

#### Scenario: Message targets RF
- **WHEN** `organization-id` is `1`
- **THEN** RF processes the message and KZ skips it without a status

#### Scenario: Message targets KZ
- **WHEN** `organization-id` is `5`
- **THEN** KZ processes the message and RF skips it without a status

#### Scenario: Organization header is absent
- **WHEN** `organization-id` is absent
- **THEN** RF and KZ independently process the same message

#### Scenario: Message targets an unknown contour
- **WHEN** a contour receives a configured code that is not its own
- **THEN** that contour records no business result and publishes no status

### Requirement: Extensible routing configuration

The `organization-id` to contour mapping MUST be stored as configurable data rather than code. Initial active mappings SHALL be `1 → RF` and `5 → KZ`. Routing MUST use one update interface that can later accept records from an organization Kafka topic without changing filter logic; consuming that future topic is outside this change.

#### Scenario: Administrator adds another organization code
- **WHEN** a new active organization-to-contour mapping is added through the supported update interface
- **THEN** subsequent messages use that mapping without a code change or extension rebuild

#### Scenario: Mapping is deactivated
- **WHEN** an `organization-id` mapping is absent or inactive
- **THEN** the contour skips that addressed message without a business status and records the filtering decision

### Requirement: Independent contour consumption

RF and KZ MUST use independent consumer groups and MUST publish outcomes independently. Status messages from RF SHALL use sender `1c-rf`; status messages from KZ SHALL use sender `1c-kz`.

#### Scenario: One contour fails independently
- **WHEN** RF completes a broadcast message and KZ cannot apply it
- **THEN** the topic contains an RF completed outcome and a KZ failed outcome for the same `correlation-id`

### Requirement: Direct Kafka consumer runtime

Each contour MUST run a continuously active 1C background consumer for `contragents` using the project Kafka external component directly. The solution MUST NOT introduce a REST bridge or depend on a ready-made industry integration extension. Consumer start, stop, and reconnect behavior MUST be controllable and observable.

#### Scenario: Contour exchange is enabled
- **WHEN** the configured background consumer starts
- **THEN** it connects through the external component and subscribes to `contragents` with that contour's consumer group

#### Scenario: External component cannot connect
- **WHEN** the background consumer cannot initialize or reach Kafka
- **THEN** it records a transport error, changes no business data, and follows the configured reconnect policy

### Requirement: Core counterparty body

The body MUST contain numeric `id` and non-blank `name`. Optional nullable fields SHALL include `uid`, `kpp`, `ogrn`, `name_short`, `is_provider`, `is_client`, `is_transporter`, `is_other_relationship`, `is_separate`, `type_entity`, `reg_number`, `head_contragent`, `additional_information`, and `country`. A supplied `uid` MUST be a UUID.

#### Scenario: Minimum valid body is received
- **WHEN** the body contains valid `id` and `name` and omits all optional fields and collections
- **THEN** it passes required-field validation and omitted collections are treated as empty

#### Scenario: Name is blank
- **WHEN** `name` is absent, null, empty, or whitespace-only
- **THEN** the message fails with `REQUIRED_FIELD_MISSING` at path `name`

#### Scenario: UID has invalid syntax
- **WHEN** optional `uid` is present but is not a UUID
- **THEN** the message fails with `INVALID_FORMAT` at path `uid`

### Requirement: Counterparty type and registration validation

`type_entity` SHALL accept only `legal`, `physical_person`, `legal_outside`, or `sole_proprietor`. Registration-number rules MUST be contour- and type-specific. An RF legal entity MUST have a valid KPP; a physical person SHALL be accepted with `reg_number`, `kpp`, and `ogrn` absent or null.

#### Scenario: RF legal entity lacks KPP
- **WHEN** RF receives a legal entity without a valid `kpp`
- **THEN** validation adds `REQUIRED_FIELD_MISSING` or `INVALID_FORMAT` at path `kpp`

#### Scenario: Physical person has no tax fields
- **WHEN** a physical person has null `reg_number`, `kpp`, and `ogrn`
- **THEN** those null values do not cause a validation failure

#### Scenario: Entity type is unknown
- **WHEN** `type_entity` contains a value outside the supported enumeration
- **THEN** validation adds `INVALID_FORMAT` at path `type_entity`

### Requirement: Contact and address snapshot

`emails`, `phones`, and `addresses` SHALL describe the complete contact snapshot. Email and phone values MUST be trimmed. Each address MUST use type `actual`, `legal`, or `postal`. An absent or null collection SHALL be treated as empty.

#### Scenario: Contact values contain surrounding spaces
- **WHEN** an otherwise valid email or phone contains leading or trailing whitespace
- **THEN** the stored value is trimmed before comparison and recording

#### Scenario: Address type is unsupported
- **WHEN** an address has a type outside `actual`, `legal`, and `postal`
- **THEN** validation adds `INVALID_FORMAT` at the address type path

### Requirement: Bank account snapshot

Every `bank_accounts` item MUST contain a stable `id` and SHALL support optional nullable `number`, `bic`, `name`, and `is_default`. The collection SHALL be the complete set for the counterparty. The exchange SHALL preserve each supplied `is_default` value subject to target-system recording rules.

#### Scenario: Bank account lacks identity
- **WHEN** a bank account item has no valid `id`
- **THEN** validation adds `REQUIRED_FIELD_MISSING` at that item path

#### Scenario: Default flag is supplied
- **WHEN** a bank account contains a valid `is_default` value
- **THEN** the adapter passes that value to the contour mapping without inventing an additional contract restriction

### Requirement: Contract snapshot

Every `contracts` item MUST have at least one stable external key in `id` or `uid`, and SHALL support `number`, `name`, `date`, `organization`, and type `realization` or `purchase`. A supplied contract `uid` MUST be a UUID.

#### Scenario: Contract has no external key
- **WHEN** a contract contains neither a valid `id` nor a valid `uid`
- **THEN** validation adds `REQUIRED_FIELD_MISSING` at that contract path

#### Scenario: Contract type is unsupported
- **WHEN** a contract type is neither `realization` nor `purchase`
- **THEN** validation adds `INVALID_FORMAT` at the contract type path

### Requirement: Contract organization resolution

A contract organization MUST contain `id` and `uid`. `organization.uid` MUST be a UUID that directly identifies a 1C organization reference, and its configured external organization code MUST equal `organization.id`. The exchange SHALL NOT infer an organization from another counterparty field.

#### Scenario: Organization reference matches
- **WHEN** `organization.uid` resolves to one organization whose configured code equals `organization.id`
- **THEN** the contract is assigned to that organization

#### Scenario: Organization reference does not exist
- **WHEN** `organization.uid` does not resolve to an existing organization
- **THEN** the message fails with `REFERENCE_NOT_FOUND` at the contract organization path

#### Scenario: Organization identifiers disagree
- **WHEN** `organization.uid` resolves but its configured code differs from `organization.id`
- **THEN** the message fails with `DUPLICATE_CONFLICT` at the contract organization path

### Requirement: Deterministic counterparty lookup

The adapter SHALL search by external `id`, then by optional `uid`, then by `reg_number + kpp`. All supplied identifiers MUST resolve to no more than one consistent counterparty. A unique fallback match SHALL be linked to the supplied external identifiers.

#### Scenario: External ID matches
- **WHEN** exactly one counterparty is linked to the supplied `id`
- **THEN** that counterparty is updated without creating another card

#### Scenario: Registration data gives one fallback match
- **WHEN** neither `id` nor `uid` is linked and exactly one card matches `reg_number + kpp`
- **THEN** that card receives the external identifiers and is updated

#### Scenario: Identifiers point to different cards
- **WHEN** supplied `id`, `uid`, or registration data resolve to different counterparties
- **THEN** no data is changed and failed contains `DUPLICATE_CONFLICT`

#### Scenario: Fallback has multiple matches
- **WHEN** more than one card matches `reg_number + kpp`
- **THEN** no card is selected and failed contains `DUPLICATE_CONFLICT`

### Requirement: Head counterparty resolution

When `head_contragent` is supplied, the adapter MUST resolve it by its external `id` and optional `uid` without creating a placeholder. A missing head SHALL be treated as a retryable dependency and SHALL end as `HEAD_CONTRAGENT_NOT_FOUND` only after the retry policy is exhausted.

#### Scenario: Head appears during retries
- **WHEN** the head counterparty is absent initially but becomes available before the final attempt
- **THEN** the child counterparty is applied with the resolved head and completes successfully

#### Scenario: Head remains absent
- **WHEN** the head counterparty cannot be resolved in any allowed attempt
- **THEN** no partial snapshot is committed and failed contains `HEAD_CONTRAGENT_NOT_FOUND` at path `head_contragent`

### Requirement: Atomic full-snapshot synchronization

Card fields and supplied collections MUST be applied in one transaction. Existing bank accounts and contracts absent from the incoming snapshot MUST receive a deletion mark (`ПометкаУдаления`) in the same transaction, including records created manually. Physical catalog deletion of those children MUST NOT be used. If a later snapshot again contains the child, the deletion mark MUST be cleared on write. If any write or soft-delete fails, the complete transaction MUST roll back.

#### Scenario: Child disappears from a newer snapshot
- **WHEN** an existing bank account or contract is absent from the accepted snapshot
- **THEN** it is marked for deletion in the same transaction as the counterparty update

#### Scenario: Empty collection is received
- **WHEN** `bank_accounts` or `contracts` is absent, null, or empty
- **THEN** all existing items of that collection for the counterparty are marked for deletion

#### Scenario: Omitted child is referenced by documents
- **WHEN** accounting references exist for an omitted child
- **THEN** the child still receives `ПометкаУдаления` and the snapshot is not rolled back solely for that reference

#### Scenario: Child returns in a later snapshot
- **WHEN** a previously marked bank account or contract appears again in an accepted snapshot
- **THEN** the deletion mark is cleared when the child is written

### Requirement: Message idempotency

The input header `id` SHALL be the idempotency key within each contour. A repeated delivery MUST NOT apply business changes twice or create a second logical status lifecycle. A compact processed-id record MUST remain after raw payload cleanup. Reuse of the same `id` with a different payload MUST NOT change the original result.

#### Scenario: Completed message is delivered again
- **WHEN** the same message `id` is received after completion
- **THEN** no business data or logical status record is created again

#### Scenario: Duplicate arrives while processing
- **WHEN** the same message `id` is delivered while its first processing attempt is active
- **THEN** only one worker owns and changes the counterparty snapshot

#### Scenario: Message ID is reused with another payload
- **WHEN** the same message `id` is received with a payload checksum different from the registered payload
- **THEN** the new delivery is quarantined without changing business data or the original logical status lifecycle

#### Scenario: Raw message retention expires
- **WHEN** raw Inbox and diagnostic payload data are removed after their retention period
- **THEN** the compact processed-id record remains able to suppress a later duplicate

### Requirement: Status lifecycle

After routing and idempotency registration, the contour MUST successfully publish one logical `contragent_exchange_started` before body validation or business writes. If Started cannot be published, business processing MUST NOT begin. The contour MUST then publish exactly one logical completed or failed outcome.

#### Scenario: Valid message completes
- **WHEN** the snapshot transaction commits
- **THEN** completed follows started for that contour and no failed outcome exists

#### Scenario: Body validation fails
- **WHEN** the routed envelope is valid but the body contains validation errors
- **THEN** started is followed by failed and no business data changes

#### Scenario: Started publication is temporarily unavailable
- **WHEN** the Started status cannot be delivered to Kafka
- **THEN** body validation and business writes remain blocked, status delivery follows the technical retry policy, and the failure is logged as a transport error separately from business errors

### Requirement: Processing stage audit

The contour MUST record `received`, `filtered_out`, `started`, `completed`, and `failed` stages in a dedicated exchange register or the 1C event log. Each event MUST identify contour, message id, correlation id, topic, partition, offset, time, and technical or business category without exposing credentials.

#### Scenario: Message is filtered by contour
- **WHEN** an addressed message does not belong to the current contour
- **THEN** the journal contains `received` and `filtered_out` and contains no `started`, `completed`, or `failed` business status stage

#### Scenario: Message completes successfully
- **WHEN** a routed snapshot is applied and Completed is published
- **THEN** the journal can reconstruct the ordered stages `received`, `started`, and `completed`

#### Scenario: Started publication fails
- **WHEN** Kafka rejects or times out the Started publication
- **THEN** the journal records a transport-category error distinct from validation or business-write errors

### Requirement: Status message contract

Each status MUST use a new message UUID, copy the input `correlation-id`, identify its contour sender, and carry `timestamp-ms`, `type`, and `version`. Started and completed bodies MUST contain counterparty `id` and optional `uid`; failed MUST additionally contain a non-empty `messages[]`.

#### Scenario: Completed status is formed
- **WHEN** a snapshot commits successfully
- **THEN** completed contains the input counterparty `id` and `uid` when supplied

#### Scenario: Failed status is formed
- **WHEN** processing reaches a terminal error
- **THEN** each `messages[]` item contains non-empty `code`, `path`, and human-readable `message`

### Requirement: Validation error aggregation

The validator MUST report all independently detectable errors in one failed status. Allowed codes SHALL be `REQUIRED_FIELD_MISSING`, `INVALID_FORMAT`, `UNSUPPORTED_VERSION`, `REFERENCE_NOT_FOUND`, `HEAD_CONTRAGENT_NOT_FOUND`, `DUPLICATE_CONFLICT`, and `INTERNAL_ERROR`.

#### Scenario: Several fields are invalid
- **WHEN** one snapshot has an absent name, malformed uid, and unsupported contract type
- **THEN** one failed status contains separate messages for all three paths

#### Scenario: Unknown error code would be emitted
- **WHEN** an internal condition has no more specific catalog code
- **THEN** it is represented as `INTERNAL_ERROR` rather than an undocumented code

### Requirement: Retry policy

Each contour MUST perform no more than three processing attempts in total for retryable technical failures and unresolved `head_contragent`, with configurable exponential delays between attempts. Validation and duplicate conflicts MUST fail without retry. Started MUST NOT be repeated between attempts.

#### Scenario: Transient failure clears
- **WHEN** a retryable technical failure occurs on the first attempt and clears on the second
- **THEN** processing completes without a second logical started status

#### Scenario: Technical retries are exhausted
- **WHEN** a retryable technical failure remains after the third attempt
- **THEN** processing ends with failed containing `INTERNAL_ERROR`

#### Scenario: Validation error is found
- **WHEN** validation returns one or more deterministic errors
- **THEN** the message fails on the first attempt without delayed retry

### Requirement: Terminal failures require explicit replay

After a terminal failed status, the contour MUST NOT automatically consume the same stored message as a new business attempt. A replay SHALL require an explicit operator action and MUST preserve the original message id for idempotency control or create a documented new message id.

#### Scenario: Message reaches terminal failure
- **WHEN** all allowed attempts are exhausted
- **THEN** the message remains available for diagnostics but is not automatically reprocessed

### Requirement: Kafka ordering key

The producer MUST use counterparty `uid` as Kafka key when present and MUST otherwise use the string form of `id`. All events for the same selected key SHALL remain ordered within one partition.

#### Scenario: UID is present
- **WHEN** a counterparty snapshot contains `uid`
- **THEN** the Kafka record key equals that `uid`

#### Scenario: UID is absent
- **WHEN** a counterparty snapshot omits `uid`
- **THEN** the Kafka record key equals the string form of counterparty `id`

### Requirement: Configurable consumer concurrency and partitioning

Consumer group id, consumer worker count, and expected `contragents` partition count MUST be configurable per contour. Startup MUST compare expected and actual partitions and expose mismatches. Processing MUST preserve increasing offset order within each partition; later records MUST NOT overtake an earlier record waiting for retry.

#### Scenario: Worker count fits the topic
- **WHEN** a contour starts with worker count not greater than the actual partition count
- **THEN** Kafka assigns partitions within that consumer group and each assigned partition is processed in offset order

#### Scenario: Worker count exceeds partitions
- **WHEN** configured worker count is greater than the actual partition count
- **THEN** startup records a configuration warning and excess workers remain idle without duplicating processing

#### Scenario: Earlier offset is waiting for retry
- **WHEN** a message at one partition offset is in `waiting_retry`
- **THEN** a later offset from that partition is not applied before the earlier message reaches a terminal state

### Requirement: Child collections stay in the counterparty topic

`contracts` and `bank_accounts` MUST be transported and processed only inside the full `contragent_created` or `contragent_updated` snapshot. This change MUST NOT introduce separate Kafka topics, consumers, or independent ordering streams for those collections.

#### Scenario: Snapshot contains child collections
- **WHEN** a counterparty message contains contracts or bank accounts
- **THEN** the same counterparty process validates and applies them atomically without reading another topic

### Requirement: Near-real-time processing without a numeric SLA

No numeric processing SLA is imposed. While exchange is enabled and capacity is available, the consumer MUST poll continuously and dispatch routing and Started publication without an intentional scheduling delay. Configured exponential delays SHALL apply only to retryable failures, not to the first processing attempt.

#### Scenario: Worker capacity is available
- **WHEN** Kafka returns a new counterparty message to an available consumer
- **THEN** routing and Started publication are dispatched in the same processing cycle without an artificial wait

#### Scenario: Message requires retry
- **WHEN** a retryable error occurs after Started
- **THEN** only the retry attempt waits for its configured backoff while unrelated available partitions continue processing

### Requirement: Contour-specific mapping

RF and KZ MUST implement the same external contract through separate mapping rules for their metadata and national registration rules. Mapping settings and contour codes MUST be changeable without modifying the shared message contract.

#### Scenario: Broadcast snapshot is valid in both countries
- **WHEN** a snapshot without `organization-id` satisfies both contour rule sets
- **THEN** each contour maps it to its own metadata and publishes its own completed status

#### Scenario: Snapshot violates only one country's rule
- **WHEN** a broadcast snapshot is valid for RF but invalid for KZ
- **THEN** RF may complete while KZ returns its own structured failed status

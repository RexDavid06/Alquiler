Phase 3 is approved.

Proceed with Phase 4 — Lease & Renewal Management API.

Important: this phase is about LEASES and LEASE LIFECYCLE only. Do not begin the full Payment, Notification, SaaS billing, Platform Admin, or React frontend phases yet.

Use the existing lease service layer and do not duplicate lease lifecycle/business logic inside views.

### 1. Lease creation

Implement API functionality for landlords to:

* Create a lease
* List leases
* Retrieve a lease
* Update a lease where business rules permit
* Terminate a lease
* Renew a lease
* View lease history

A landlord may only create/manage leases involving:

* their own property
* their own unit
* tenants associated with their tenancy/invitation domain as allowed by the established architecture

Never trust landlord/property/unit/tenant IDs from the client without validating ownership and relationships.

### 2. Lease creation rules

Before creating a lease, enforce:

* Landlord owns the property.
* Unit belongs to the property.
* Tenant is a valid TENANT account.
* Unit is eligible for tenancy.
* No conflicting active tenancy exists.
* Start date and expiry date are valid.
* Rent amount is valid.
* Currency is valid ISO-3.
* Rent due day is valid.
* Rent frequency is valid.
* Subscription/business rules are respected where applicable.

Use the existing:

create_lease()

service.

Do not duplicate its transaction/validation logic in the API layer.

### 3. IMPORTANT — future leases

Review the existing effective_status() implementation.

A lease with a future start_date must NOT be treated as an active tenancy before its start date.

We need to distinguish:

* FUTURE
* ACTIVE
* EXPIRING
* EXPIRED
* TERMINATED

If the existing status enum/model does not explicitly contain FUTURE, determine the cleanest approach without unnecessarily breaking the established schema.

This distinction must be correct for:

* unit occupancy
* active tenant counts
* subscription limits
* dashboards
* lease filtering
* rent schedules

Explain the chosen approach before making a significant schema change.

### 4. Unit occupancy

Occupancy must remain backend-controlled.

The API must not allow a landlord/client to manually mark a unit OCCUPIED or VACANT.

The lease lifecycle remains the source of truth.

Verify that:

* future lease → unit should not become occupied prematurely
* active lease → unit becomes occupied
* expired/terminated lease → unit becomes vacant when appropriate
* renewal does not temporarily make the unit vacant incorrectly

### 5. Lease renewal

Implement renewal using the existing renew_lease() service.

A renewal must:

* preserve the original lease
* create a new lease/history record rather than overwriting history
* link the new lease to the previous lease
* prevent overlapping active leases
* preserve tenant/property/unit relationships
* correctly transition the previous lease
* correctly establish the new lease dates
* correctly synchronize occupancy

Test edge cases carefully.

Do NOT allow a renewal to silently create two active leases for the same unit.

### 6. Lease termination

Implement termination through terminate_lease().

Termination must:

* preserve the lease record
* record the appropriate termination state/date if already supported
* release occupancy when appropriate
* prevent future accidental modifications that violate history
* preserve the relationship for reporting/history

Do not hard-delete leases.

### 7. Lease updates

Be careful about what can be edited after a lease becomes active.

Do not allow a normal PATCH/PUT to bypass:

* date validation
* unit conflicts
* rent rules
* tenant/property ownership
* historical integrity

If certain fields should become immutable once a lease is active, enforce that server-side.

Explain which fields are mutable and which are immutable.

### 8. Lease history

Provide a way to view renewal/history relationships.

For example:

Lease A
↓ previous_lease = null

Lease B
↓ previous_lease = Lease A

Lease C
↓ previous_lease = Lease B

The API should make this relationship usable by the future frontend.

### 9. Rent schedule visibility

The full Rent & Payment phase is Phase 5, so do NOT build payment functionality yet.

However, the lease API should expose appropriate lease rent information and, if already supported by the existing model/service, read-only rent schedule information.

Do not duplicate rent schedule generation logic.

Use the existing payments service where appropriate.

### 10. Authorization and isolation

Test:

1. Landlord A can manage their own leases.
2. Landlord A cannot retrieve Landlord B's lease.
3. Landlord A cannot modify Landlord B's lease.
4. Landlord A cannot terminate Landlord B's lease.
5. Landlord A cannot renew Landlord B's lease.
6. Landlord A cannot create a lease using Landlord B's property.
7. Landlord A cannot create a lease using Landlord B's unit.
8. Landlord A cannot use another landlord's tenant inappropriately.
9. Tenant cannot perform landlord lease-management operations.
10. Tenant can only see leases they are authorized to see.
11. Unauthenticated users are rejected.

Use queryset/service-level authorization. Never rely on frontend filtering.

### 11. API design

Implement appropriate REST endpoints under:

/api/v1/leases/

/api/v1/leases/{id}/

/api/v1/leases/{id}/renew/

/api/v1/leases/{id}/terminate/

/api/v1/leases/{id}/history/

Use serializers, views, permissions, filtering, search, ordering, pagination, validation, and OpenAPI documentation.

Keep the API reusable for the future React frontend AND mobile application.

### 12. Status filtering

Support useful lease status filtering:

* FUTURE (if implemented)
* ACTIVE
* EXPIRING
* EXPIRED
* TERMINATED

Also support useful filters such as:

* property
* unit
* tenant
* rent frequency
* start date
* expiry date

Do not allow clients to arbitrarily set calculated lifecycle status.

### 13. Tests

Write comprehensive automated tests.

At minimum:

* lease creation
* successful lease creation
* invalid dates
* invalid rent values
* invalid currency
* wrong property/unit relationship
* cross-landlord isolation
* tenant authorization
* conflicting active lease
* future lease behavior
* active lease behavior
* expiring lease behavior
* expired lease behavior
* termination
* renewal
* renewal history
* renewal conflict
* occupancy synchronization
* immutable/protected fields
* pagination/filtering/order
* authentication requirements

Pay special attention to date-boundary tests.

### 14. Database/migrations

Avoid unnecessary schema changes.

If the FUTURE lease state or any other correction requires a schema change:

* explain it
* implement it carefully
* generate migrations
* apply them
* run makemigrations --check --dry-run

### 15. Completion criteria

Do not mark Phase 4 complete until:

* Lease CRUD/lifecycle APIs work.
* Create/renew/terminate use the service layer.
* Future/active/expiring/expired/terminated behavior is correct.
* Unit occupancy is correct.
* Renewal history is preserved.
* Lease conflicts are prevented.
* Cross-landlord isolation is tested.
* Automated tests pass.
* OpenAPI documentation is updated.
* No migration drift exists.

At the end provide:

### Implemented

### Endpoints

### Lease lifecycle rules

### Status model

### Renewal behavior

### Occupancy behavior

### Authorization/data isolation

### Automated test results

### Migrations

### Known issues

### Next recommended step

Stop after Phase 4 and wait for review.

Do not begin Phase 5 automatically.

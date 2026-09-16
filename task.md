We are preparing Alquiler for a DEMO / PITCH-READY stage.

Important strategic decision:

We are NOT launching to paying customers yet.

For now:

* Use free hosting tiers where practical.
* Do NOT integrate Paystack yet.
* Do NOT spend money on infrastructure yet.
* The application should be stable enough to demonstrate to prospective landlords/property managers.
* The architecture and code should still be production-minded so we can upgrade infrastructure later without rewriting the application.

The eventual paid production launch will be a separate phase.

Your job is to inspect the entire repository and make the project clean, stable, portable, and ready for free-tier deployment/demo.

==================================================

1. FIRST: INSPECT BEFORE CHANGING
   ==================================================

Inspect:

backend/
mobile/
frontend/ (or the actual frontend directory)
docker-compose.yml
Dockerfiles
.env files
.gitignore
package.json files
requirements files
Django settings
URL configuration
authentication
database models/migrations
tests
existing deployment configuration
existing documentation

Understand the current architecture before making changes.

Do NOT perform broad unrelated refactors.

Do NOT reset/revert unrelated work.

Do NOT delete files simply because they look unfamiliar.

==================================================
2. FREE-TIER DEMO ARCHITECTURE
==============================

Prepare the application for a free-tier deployment approximately like:

Frontend:

* free static hosting

Backend:

* free web/API hosting

Database:

* free PostgreSQL tier

Redis:

* free tier if actually required by the current application
* otherwise document whether Redis can be temporarily omitted for the demo environment

Mobile:

* Expo Go during development/demo
* production EAS build is NOT required yet

Payments:

* manual rent/payment recording only
* NO Paystack integration

The exact provider does not need to be selected yet if doing so would unnecessarily couple the code to one provider.

Keep deployment provider-independent.

==================================================
3. DATABASE PORTABILITY — VERY IMPORTANT
========================================

Alquiler must own its data.

Do NOT design the project around a hosting provider's database.

PostgreSQL should remain the authoritative datastore.

Verify that the project supports:

* Django migrations
* PostgreSQL
* database backup
* database restore
* moving the database to another PostgreSQL provider

Document a reliable:

pg_dump
+
restore

workflow.

Example:

alquiler_YYYY-MM-DD.sql

The backup must NOT be committed to Git.

Document how to move:

Current Host
↓
PostgreSQL dump
↓
backup.sql
↓
New Host PostgreSQL
↓
restore
↓
configure DATABASE_URL
↓
python manage.py migrate
↓
verify data

==================================================
4. OPTIONAL APPLICATION JSON EXPORT
===================================

Investigate whether an application-level JSON export/import tool would be useful.

If safe and reasonably simple, implement:

python manage.py export_data --output backup.json

and:

python manage.py import_data backup.json

Requirements:

* preserve relationships
* handle foreign keys safely
* preserve stable identifiers where appropriate
* preserve important timestamps
* do NOT export passwords
* do NOT export authentication secrets
* do NOT export API keys
* validate data before import
* use transactions where appropriate
* document limitations

IMPORTANT:

JSON is NOT the authoritative backup.

PostgreSQL dump/restore remains the authoritative full migration mechanism.

If JSON import/export would create unnecessary complexity or data-integrity risks, don't implement it. Instead document PostgreSQL dump/restore clearly.

==================================================
5. ENVIRONMENT CONFIGURATION
============================

Audit all environment variables.

Remove hardcoded development URLs from production configuration.

Development may use:

localhost
127.0.0.1
192.168.0.118

but these must never be required for the deployed demo environment.

Ensure configuration supports:

DEBUG=False
SECRET_KEY from environment
ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS
SITE_URL
PostgreSQL
Redis where required
email configuration
secure proxy configuration

Do not commit actual secrets.

Update `.env.example` files with safe placeholders.

==================================================
6. MOBILE CONFIGURATION
=======================

Inspect the Expo mobile application.

Ensure:

* localhost is only a development fallback
* LAN IP is only a local development configuration
* deployed backend URL comes from environment/configuration
* no secret is bundled into the mobile app
* registration/login use the correct production API contract
* backend validation errors are not incorrectly displayed as "Network Error"

Do NOT break the current working Expo Go setup.

Do NOT delete `mobile/rex-david/` unless you first prove it is unused.

Inspect `mobile/expo.txt`.

If it contains a plaintext password or other secret:

* remove it if unnecessary
* ensure it is ignored by Git
* check whether the secret was committed
* do not expose the secret value in your final report
* recommend rotation if it was ever committed

==================================================
7. AUTHENTICATION / REGISTRATION
================================

Verify the recently fixed landlord registration flow.

The mobile app is specifically a LANDLORD application.

The user should NOT select their role during registration.

The backend should remain authoritative and assign:

role = landlord

server-side.

A client must not be able to register as an arbitrary privileged role such as admin.

Test:

* landlord registration
* duplicate email
* invalid input
* login
* logout
* expired/invalid authentication
* protected endpoints

==================================================
8. SECURITY / DATA ISOLATION
============================

Audit the application for basic production/demo safety.

Especially verify:

Landlord A cannot access:

* Landlord B's properties
* Landlord B's units
* Landlord B's tenants
* Landlord B's leases
* Landlord B's payments
* Landlord B's maintenance records

Check:

* permissions
* queryset filtering
* object ownership
* authentication
* CORS
* CSRF
* password handling
* invitation tokens
* password reset tokens
* sensitive logging

Do not weaken security to make testing easier.

==================================================
9. PRODUCTION-MINDED DJANGO SETTINGS
====================================

Ensure the project can run safely with:

DEBUG=False

Verify:

* SECRET_KEY
* ALLOWED_HOSTS
* CORS
* CSRF trusted origins
* secure proxy headers
* HTTPS behavior
* static files
* media configuration
* database configuration
* email configuration

Do not require production secrets in the repository.

==================================================
10. EMAIL
=========

Inspect:

* tenant invitations
* password reset
* account-related emails

Document exactly what SMTP environment variables will be required later.

For the free demo environment:

If SMTP is unavailable, make the limitation clear.

Do not silently pretend emails work when they don't.

Do not add a fake production email service.

==================================================
11. HEALTH CHECK
================

Inspect whether there is a safe health endpoint.

If there isn't one, add a minimal endpoint such as:

GET /health/

It must not expose secrets or sensitive database information.

It should be useful for free hosting health checks.

Do not over-engineer this.

==================================================
12. ERROR HANDLING
==================

Audit the mobile API client and backend responses.

A HTTP 400/401/403/404/500 response should not automatically become:

"Network error."

Network errors should be distinguished from actual HTTP API errors.

Make validation errors understandable to the user.

Preserve useful backend error details without exposing sensitive internals.

==================================================
13. TESTING
===========

Run the project's actual test suites.

Backend:

python manage.py test

and:

python manage.py makemigrations --check

Run pytest too if the project uses pytest.

Frontend:

Use the project's actual TypeScript/build/test commands.

Mobile:

npx tsc --noEmit

and:

npx expo export

if compatible with the current project.

Do not invent test commands.

Fix failures introduced by your changes.

Do not hide failing tests.

==================================================
14. DOCKER
==========

Inspect the existing Docker configuration.

Do NOT redesign it unnecessarily.

Verify that the application can still run with:

Django/Gunicorn
PostgreSQL
Redis where required

The Docker setup should remain useful later when we move from free hosting to paid production infrastructure.

==================================================
15. DOCUMENTATION
=================

Create/update a clear deployment document for the CURRENT free-tier demo stage.

Document:

* required environment variables
* local development
* backend deployment
* frontend deployment
* PostgreSQL setup
* Redis requirements
* database backup
* database restore
* migration between hosting providers
* health check
* static/media handling
* email limitations
* mobile API configuration
* known free-tier limitations

Also document the future upgrade path:

FREE DEMO
↓
REAL CLIENT
↓
PAID INFRASTRUCTURE
↓
PAYSTACK
↓
PRODUCTION MONITORING/BACKUPS

==================================================
16. DO NOT DO THESE YET
=======================

Do NOT:

* integrate Paystack
* deploy a paid VPS
* purchase infrastructure
* create production payment webhooks
* redesign the application architecture
* rewrite working features
* remove working Expo functionality
* add unnecessary dependencies
* add complex infrastructure just for the sake of "production readiness"

==================================================
17. FINAL REVIEW
================

After implementation:

1. Inspect git diff.
2. Check git status.
3. Confirm no secrets are tracked.
4. Confirm no plaintext passwords remain in unnecessary files.
5. Run Django checks.
6. Run migration checks.
7. Run backend tests.
8. Run frontend tests/build.
9. Run mobile TypeScript/export checks.
10. Verify database backup/restore documentation.
11. Verify Docker configuration.
12. Verify health endpoint.
13. Verify landlord registration.
14. Verify authentication.
15. Verify landlord data isolation.

Then give me a final report containing:

A. What you changed
B. Files changed
C. Security issues found
D. Registration/auth fixes
E. Database portability solution
F. Backup/restore instructions
G. Whether JSON export/import was implemented
H. Free-tier deployment readiness
I. Tests run and results
J. Remaining issues/blockers
K. What should be done later when we have a real client

Do not integrate Paystack.

Do not deploy anything yet.

Make the changes directly in the repository and test them.

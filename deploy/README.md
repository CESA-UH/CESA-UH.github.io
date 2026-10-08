# Free deployment: Render + Supabase

The backend and public CESA pages are served from the same Render web service. GitHub Pages can continue serving the existing public course pages. `render.yaml` selects the **Free** instance; it does not provision Render's expiring free database.

1. Create a Supabase Free project and a **private** Storage bucket named `hamdars-files`, with a 50 MB file limit. Keep the `hamdars` database schema outside the Data API's exposed schemas. No public bucket or browser service key is needed: the backend serves the published course downloads and authorizes every edit.
2. Use the PostgreSQL **session pooler** connection string (port 5432, IPv4 compatible) with TLS (`sslmode=require`) as Render's private `DATABASE_URL`. Store the project's HTTPS URL and server-only service key in `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
3. Deploy a Render Blueprint from this repository/branch. Supply the private admin password and Verbo API key in the Dashboard prompts. JWT signing secret is generated once by Render; retain it across deployments. Never commit passwords, API keys, database dumps, or `.env` files.
4. On initial startup, the app creates its tables in the private `hamdars` schema, creates the configured administrator, and imports the public CESA courses and PDFs. Later restarts preserve the administrator's password and all existing course data. Existing local student records are **not automatically migrated or published**; transfer them separately through an authenticated database connection if needed.
5. Once Render reports Healthy, verify `/health`, anonymous `/`, all three course pages, admin sign-in, editing, and a file upload/download after a restart. Set `assets/js/assistant-config.js`'s `backendUrl` to the deployed HTTPS origin for GitHub Pages visitors. The jointly hosted pages automatically use their own origin.

Render Free sleeps after 15 minutes of inactivity. Queued reports remain in PostgreSQL and resume when the web service starts again. Files uploaded to the course pages are streamed to Supabase Storage and do not rely on Render's temporary disk. Database, file storage, bandwidth and outbound API traffic remain subject to free-plan limits.

Local setup and data stay in the original assessment project. This directory contains only deployable source and public course assets.

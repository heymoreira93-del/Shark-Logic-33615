-- DealShark SaaS — full multi-tenant schema
-- Every company (organization) owns its users-via-membership, leads, deals,
-- contacts, files, and settings. RLS enforces organization_id isolation.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Core tenancy
-- ---------------------------------------------------------------------------

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Global permission catalog (not tenant-owned; keys are stable product capabilities)
create table if not exists public.permissions (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now()
);

-- Roles: system roles have organization_id IS NULL; custom roles are per-org
create table if not exists public.roles (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations (id) on delete cascade,
  key text not null,
  name text not null,
  description text not null default '',
  is_system boolean not null default false,
  created_at timestamptz not null default now(),
  unique (organization_id, key)
);

-- Allow one system row per key (organization_id NULL)
create unique index if not exists roles_system_key_uidx
  on public.roles (key)
  where organization_id is null;

create table if not exists public.role_permissions (
  role_id uuid not null references public.roles (id) on delete cascade,
  permission_id uuid not null references public.permissions (id) on delete cascade,
  organization_id uuid references public.organizations (id) on delete cascade,
  primary key (role_id, permission_id)
);

create table if not exists public.organization_members (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role_id uuid not null references public.roles (id),
  status text not null default 'active'
    check (status in ('active', 'invited', 'suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create index if not exists organization_members_user_idx
  on public.organization_members (user_id);

create index if not exists organization_members_org_idx
  on public.organization_members (organization_id);

-- User profile: identity + active org selection (membership is source of truth)
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  full_name text not null default '',
  current_organization_id uuid references public.organizations (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Tenant data (all require organization_id)
-- ---------------------------------------------------------------------------

create table if not exists public.organization_settings (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null unique references public.organizations (id) on delete cascade,
  assignor_name text not null default 'DealShark Acquisitions',
  default_assignment_fee numeric not null default 10000,
  default_emd numeric not null default 2500,
  notify_phone text not null default '',
  timezone text not null default 'America/New_York',
  branding jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  kind text not null default 'seller'
    check (kind in ('seller', 'buyer', 'agent', 'title', 'other')),
  full_name text not null default '',
  email text not null default '',
  phone text not null default '',
  company_name text not null default '',
  notes text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  contact_id uuid references public.contacts (id) on delete set null,
  address text not null,
  zip_code text not null default '',
  arv numeric not null default 0,
  mao numeric not null default 0,
  wholesale_fee numeric not null default 10000,
  risk_level text not null default '',
  flood_risk boolean not null default false,
  status text not null default 'New Lead',
  seller_name text not null default '',
  seller_phone text not null default '',
  last_contacted timestamptz,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.deals (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  lead_id uuid references public.leads (id) on delete set null,
  contact_id uuid references public.contacts (id) on delete set null,
  address text not null,
  price numeric not null default 0,
  seller_name text not null default '',
  seller_phone text not null default '',
  buyer_name text not null default '',
  status text not null default 'PENDING',
  signature text not null default '',
  signed_at timestamptz,
  emd numeric not null default 2500,
  closing_date text not null default '',
  deal_kind text not null default 'purchase'
    check (deal_kind in ('purchase', 'assignment')),
  assignment_fee numeric not null default 0,
  assignee_email text not null default '',
  sign_token text not null unique default encode(gen_random_bytes(24), 'hex'),
  emd_paid boolean not null default false,
  stripe_session_id text not null default '',
  notes text not null default '',
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.files (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  deal_id uuid references public.deals (id) on delete set null,
  lead_id uuid references public.leads (id) on delete set null,
  contact_id uuid references public.contacts (id) on delete set null,
  storage_path text not null,
  file_name text not null,
  content_type text not null default 'application/octet-stream',
  byte_size bigint not null default 0,
  kind text not null default 'document'
    check (kind in ('document', 'contract', 'assignment', 'title_packet', 'other')),
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.offer_queue (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  lead_id uuid references public.leads (id) on delete set null,
  deal_id uuid references public.deals (id) on delete set null,
  address text not null default '',
  phone text not null default '',
  seller_name text not null default '',
  offer_price numeric not null default 0,
  sms_preview text not null default '',
  status text not null default 'QUEUED',
  error text not null default '',
  created_at timestamptz not null default now(),
  sent_at timestamptz
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  actor_user_id uuid references auth.users (id) on delete set null,
  action text not null,
  entity_type text not null default '',
  entity_id text not null default '',
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists contacts_org_idx on public.contacts (organization_id, created_at desc);
create index if not exists leads_org_idx on public.leads (organization_id, created_at desc);
create index if not exists deals_org_idx on public.deals (organization_id, created_at desc);
create index if not exists deals_sign_token_idx on public.deals (sign_token);
create index if not exists files_org_idx on public.files (organization_id, created_at desc);
create index if not exists offer_queue_org_idx on public.offer_queue (organization_id, status);
create index if not exists audit_logs_org_idx on public.audit_logs (organization_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Seed system roles + permissions
-- ---------------------------------------------------------------------------

insert into public.permissions (key, name, description) values
  ('org.manage', 'Manage organization', 'Update org settings and billing profile'),
  ('members.manage', 'Manage members', 'Invite, remove, and change member roles'),
  ('leads.read', 'Read leads', 'View leads'),
  ('leads.write', 'Write leads', 'Create and update leads'),
  ('deals.read', 'Read deals', 'View deals'),
  ('deals.write', 'Write deals', 'Create and update deals'),
  ('contacts.read', 'Read contacts', 'View contacts'),
  ('contacts.write', 'Write contacts', 'Create and update contacts'),
  ('files.read', 'Read files', 'View and download files'),
  ('files.write', 'Write files', 'Upload and attach files'),
  ('settings.read', 'Read settings', 'View organization settings'),
  ('settings.write', 'Write settings', 'Update organization settings'),
  ('sms.send', 'Send SMS', 'Send offer and follow-up SMS'),
  ('audit.read', 'Read audit log', 'View audit events')
on conflict (key) do nothing;

insert into public.roles (organization_id, key, name, description, is_system)
select null, v.key, v.name, v.description, true
from (
  values
    ('owner', 'Owner', 'Full access to the organization'),
    ('admin', 'Admin', 'Manage members, settings, and all deal data'),
    ('agent', 'Agent', 'Work leads, deals, contacts, and files'),
    ('viewer', 'Viewer', 'Read-only access')
) as v(key, name, description)
where not exists (
  select 1 from public.roles r where r.organization_id is null and r.key = v.key
);

-- Attach permissions to system roles
insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null and r.key = 'owner'
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'admin'
  and p.key <> 'org.manage'
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'agent'
  and p.key in (
    'leads.read', 'leads.write',
    'deals.read', 'deals.write',
    'contacts.read', 'contacts.write',
    'files.read', 'files.write',
    'settings.read', 'sms.send'
  )
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'viewer'
  and p.key in (
    'leads.read', 'deals.read', 'contacts.read', 'files.read', 'settings.read'
  )
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- Tenant helper functions
-- ---------------------------------------------------------------------------

create or replace function public.is_org_member(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members m
    where m.organization_id = target_org
      and m.user_id = auth.uid()
      and m.status = 'active'
  );
$$;

create or replace function public.user_organization_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select m.organization_id
  from public.organization_members m
  where m.user_id = auth.uid()
    and m.status = 'active';
$$;

create or replace function public.current_organization_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (
      select p.current_organization_id
      from public.profiles p
      where p.id = auth.uid()
        and p.current_organization_id in (select public.user_organization_ids())
    ),
    (select public.user_organization_ids() limit 1)
  );
$$;

create or replace function public.has_org_permission(target_org uuid, permission_key text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members m
    join public.role_permissions rp on rp.role_id = m.role_id
    join public.permissions p on p.id = rp.permission_id
    where m.organization_id = target_org
      and m.user_id = auth.uid()
      and m.status = 'active'
      and p.key = permission_key
  );
$$;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists organizations_set_updated_at on public.organizations;
create trigger organizations_set_updated_at
  before update on public.organizations
  for each row execute function public.set_updated_at();

drop trigger if exists organization_members_set_updated_at on public.organization_members;
create trigger organization_members_set_updated_at
  before update on public.organization_members
  for each row execute function public.set_updated_at();

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

drop trigger if exists organization_settings_set_updated_at on public.organization_settings;
create trigger organization_settings_set_updated_at
  before update on public.organization_settings
  for each row execute function public.set_updated_at();

drop trigger if exists contacts_set_updated_at on public.contacts;
create trigger contacts_set_updated_at
  before update on public.contacts
  for each row execute function public.set_updated_at();

drop trigger if exists leads_set_updated_at on public.leads;
create trigger leads_set_updated_at
  before update on public.leads
  for each row execute function public.set_updated_at();

drop trigger if exists deals_set_updated_at on public.deals;
create trigger deals_set_updated_at
  before update on public.deals
  for each row execute function public.set_updated_at();

-- Provision org + owner membership + settings on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  org_id uuid;
  org_name text;
  org_slug text;
  owner_role_id uuid;
begin
  org_name := coalesce(
    nullif(trim(new.raw_user_meta_data->>'full_name'), ''),
    split_part(new.email, '@', 1),
    'DealShark Org'
  );
  org_slug := lower(regexp_replace(org_name || '-' || substr(new.id::text, 1, 8), '[^a-z0-9]+', '-', 'g'));

  insert into public.organizations (name, slug)
  values (org_name || ' Workspace', org_slug)
  returning id into org_id;

  insert into public.organization_settings (organization_id)
  values (org_id);

  select id into owner_role_id
  from public.roles
  where organization_id is null and key = 'owner'
  limit 1;

  insert into public.organization_members (organization_id, user_id, role_id, status)
  values (org_id, new.id, owner_role_id, 'active');

  insert into public.profiles (id, email, full_name, current_organization_id)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    org_id
  );

  insert into public.audit_logs (organization_id, actor_user_id, action, entity_type, entity_id, meta)
  values (
    org_id,
    new.id,
    'organization.created',
    'organization',
    org_id::text,
    jsonb_build_object('source', 'signup')
  );

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table public.organizations enable row level security;
alter table public.permissions enable row level security;
alter table public.roles enable row level security;
alter table public.role_permissions enable row level security;
alter table public.organization_members enable row level security;
alter table public.profiles enable row level security;
alter table public.organization_settings enable row level security;
alter table public.contacts enable row level security;
alter table public.leads enable row level security;
alter table public.deals enable row level security;
alter table public.files enable row level security;
alter table public.offer_queue enable row level security;
alter table public.audit_logs enable row level security;

-- Permissions catalog: authenticated users can read
drop policy if exists permissions_read_authenticated on public.permissions;
create policy permissions_read_authenticated on public.permissions
  for select to authenticated
  using (true);

-- System + org roles visible to members
drop policy if exists roles_select_visible on public.roles;
create policy roles_select_visible on public.roles
  for select to authenticated
  using (
    organization_id is null
    or public.is_org_member(organization_id)
  );

drop policy if exists role_permissions_select_visible on public.role_permissions;
create policy role_permissions_select_visible on public.role_permissions
  for select to authenticated
  using (
    organization_id is null
    or public.is_org_member(organization_id)
  );

-- Organizations: members can read; owners/admins with org.manage can update
drop policy if exists organizations_select_member on public.organizations;
create policy organizations_select_member on public.organizations
  for select to authenticated
  using (public.is_org_member(id));

drop policy if exists organizations_update_manage on public.organizations;
create policy organizations_update_manage on public.organizations
  for update to authenticated
  using (public.has_org_permission(id, 'org.manage'))
  with check (public.has_org_permission(id, 'org.manage'));

-- Members
drop policy if exists organization_members_select on public.organization_members;
create policy organization_members_select on public.organization_members
  for select to authenticated
  using (public.is_org_member(organization_id));

drop policy if exists organization_members_manage on public.organization_members;
create policy organization_members_manage on public.organization_members
  for all to authenticated
  using (public.has_org_permission(organization_id, 'members.manage'))
  with check (public.has_org_permission(organization_id, 'members.manage'));

-- Profiles: user can read/update self; org members can read teammate profiles
drop policy if exists profiles_select_self_or_teammate on public.profiles;
create policy profiles_select_self_or_teammate on public.profiles
  for select to authenticated
  using (
    id = auth.uid()
    or exists (
      select 1
      from public.organization_members me
      join public.organization_members them
        on them.organization_id = me.organization_id
      where me.user_id = auth.uid()
        and me.status = 'active'
        and them.user_id = profiles.id
        and them.status = 'active'
    )
  );

drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

-- Generic tenant isolation helpers via policies
drop policy if exists organization_settings_select on public.organization_settings;
create policy organization_settings_select on public.organization_settings
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'settings.read')
  );

drop policy if exists organization_settings_write on public.organization_settings;
create policy organization_settings_write on public.organization_settings
  for all to authenticated
  using (public.has_org_permission(organization_id, 'settings.write'))
  with check (public.has_org_permission(organization_id, 'settings.write'));

drop policy if exists contacts_select on public.contacts;
create policy contacts_select on public.contacts
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'contacts.read')
  );

drop policy if exists contacts_write on public.contacts;
create policy contacts_write on public.contacts
  for all to authenticated
  using (public.has_org_permission(organization_id, 'contacts.write'))
  with check (public.has_org_permission(organization_id, 'contacts.write'));

drop policy if exists leads_select on public.leads;
create policy leads_select on public.leads
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'leads.read')
  );

drop policy if exists leads_write on public.leads;
create policy leads_write on public.leads
  for all to authenticated
  using (public.has_org_permission(organization_id, 'leads.write'))
  with check (public.has_org_permission(organization_id, 'leads.write'));

drop policy if exists deals_select on public.deals;
create policy deals_select on public.deals
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'deals.read')
  );

drop policy if exists deals_write on public.deals;
create policy deals_write on public.deals
  for all to authenticated
  using (public.has_org_permission(organization_id, 'deals.write'))
  with check (public.has_org_permission(organization_id, 'deals.write'));

drop policy if exists files_select on public.files;
create policy files_select on public.files
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'files.read')
  );

drop policy if exists files_write on public.files;
create policy files_write on public.files
  for all to authenticated
  using (public.has_org_permission(organization_id, 'files.write'))
  with check (public.has_org_permission(organization_id, 'files.write'));

drop policy if exists offer_queue_all on public.offer_queue;
create policy offer_queue_all on public.offer_queue
  for all to authenticated
  using (public.is_org_member(organization_id))
  with check (public.is_org_member(organization_id));

drop policy if exists audit_logs_select on public.audit_logs;
create policy audit_logs_select on public.audit_logs
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'audit.read')
  );

drop policy if exists audit_logs_insert on public.audit_logs;
create policy audit_logs_insert on public.audit_logs
  for insert to authenticated
  with check (public.is_org_member(organization_id));

grant execute on function public.is_org_member(uuid) to authenticated;
grant execute on function public.user_organization_ids() to authenticated;
grant execute on function public.current_organization_id() to authenticated;
grant execute on function public.has_org_permission(uuid, text) to authenticated;

grant usage on schema public to authenticated;
grant select on public.permissions to authenticated;
grant select on public.roles to authenticated;
grant select on public.role_permissions to authenticated;
grant select, update on public.organizations to authenticated;
grant select, insert, update, delete on public.organization_members to authenticated;
grant select, update on public.profiles to authenticated;
grant select, insert, update, delete on public.organization_settings to authenticated;
grant select, insert, update, delete on public.contacts to authenticated;
grant select, insert, update, delete on public.leads to authenticated;
grant select, insert, update, delete on public.deals to authenticated;
grant select, insert, update, delete on public.files to authenticated;
grant select, insert, update, delete on public.offer_queue to authenticated;
grant select, insert on public.audit_logs to authenticated;

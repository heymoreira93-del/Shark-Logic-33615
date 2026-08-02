-- Complete authz model: Owner / Admin / Manager / Employee / Viewer
-- Permissions: View/Edit/Delete Leads, View/Edit Deals, Manage Users, Billing, Settings

-- Ensure permission catalog matches product matrix
insert into public.permissions (key, name, description) values
  ('leads.view', 'View Leads', 'View leads in the organization'),
  ('leads.edit', 'Edit Leads', 'Create and update leads'),
  ('leads.delete', 'Delete Leads', 'Delete leads'),
  ('deals.view', 'View Deals', 'View deals in the organization'),
  ('deals.edit', 'Edit Deals', 'Create and update deals'),
  ('users.manage', 'Manage Users', 'Invite, remove, and change member roles'),
  ('billing.manage', 'Billing', 'View and manage billing'),
  ('settings.manage', 'Settings', 'View and update organization settings')
on conflict (key) do update
set name = excluded.name,
    description = excluded.description;

-- System roles
insert into public.roles (organization_id, key, name, description, is_system)
select null, v.key, v.name, v.description, true
from (
  values
    ('owner', 'Owner', 'Full access including billing and user management'),
    ('admin', 'Admin', 'Full operational access; manage users and settings'),
    ('manager', 'Manager', 'Manage leads and deals; update settings'),
    ('employee', 'Employee', 'Work leads and deals'),
    ('viewer', 'Viewer', 'Read-only access to leads and deals')
) as v(key, name, description)
where not exists (
  select 1 from public.roles r where r.organization_id is null and r.key = v.key
);

-- Retire legacy role keys from new assignments (keep rows if already referenced)
-- Clear and rebuild system role_permissions for the five roles above
delete from public.role_permissions rp
using public.roles r
where rp.role_id = r.id
  and r.organization_id is null
  and r.key in ('owner', 'admin', 'manager', 'employee', 'viewer', 'agent');

-- Owner: everything
insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'owner'
  and p.key in (
    'leads.view', 'leads.edit', 'leads.delete',
    'deals.view', 'deals.edit',
    'users.manage', 'billing.manage', 'settings.manage'
  );

-- Admin: all except billing
insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'admin'
  and p.key in (
    'leads.view', 'leads.edit', 'leads.delete',
    'deals.view', 'deals.edit',
    'users.manage', 'settings.manage'
  );

-- Manager: leads+deals+settings (no user/billing admin)
insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'manager'
  and p.key in (
    'leads.view', 'leads.edit', 'leads.delete',
    'deals.view', 'deals.edit',
    'settings.manage'
  );

-- Employee: work leads/deals, no delete/users/billing/settings
insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'employee'
  and p.key in (
    'leads.view', 'leads.edit',
    'deals.view', 'deals.edit'
  );

-- Viewer: read-only
insert into public.role_permissions (role_id, permission_id, organization_id)
select r.id, p.id, null
from public.roles r
cross join public.permissions p
where r.organization_id is null
  and r.key = 'viewer'
  and p.key in ('leads.view', 'deals.view');

-- Replace RLS policies to use the new permission keys
drop policy if exists leads_select on public.leads;
drop policy if exists leads_write on public.leads;
create policy leads_select on public.leads
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'leads.view')
  );
create policy leads_insert on public.leads
  for insert to authenticated
  with check (public.has_org_permission(organization_id, 'leads.edit'));
create policy leads_update on public.leads
  for update to authenticated
  using (public.has_org_permission(organization_id, 'leads.edit'))
  with check (public.has_org_permission(organization_id, 'leads.edit'));
create policy leads_delete on public.leads
  for delete to authenticated
  using (public.has_org_permission(organization_id, 'leads.delete'));

drop policy if exists deals_select on public.deals;
drop policy if exists deals_write on public.deals;
create policy deals_select on public.deals
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'deals.view')
  );
create policy deals_insert on public.deals
  for insert to authenticated
  with check (public.has_org_permission(organization_id, 'deals.edit'));
create policy deals_update on public.deals
  for update to authenticated
  using (public.has_org_permission(organization_id, 'deals.edit'))
  with check (public.has_org_permission(organization_id, 'deals.edit'));
create policy deals_delete on public.deals
  for delete to authenticated
  using (public.has_org_permission(organization_id, 'deals.edit'));

drop policy if exists contacts_select on public.contacts;
drop policy if exists contacts_write on public.contacts;
create policy contacts_select on public.contacts
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'leads.view')
  );
create policy contacts_write on public.contacts
  for all to authenticated
  using (public.has_org_permission(organization_id, 'leads.edit'))
  with check (public.has_org_permission(organization_id, 'leads.edit'));

drop policy if exists files_select on public.files;
drop policy if exists files_write on public.files;
create policy files_select on public.files
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and public.has_org_permission(organization_id, 'deals.view')
  );
create policy files_write on public.files
  for all to authenticated
  using (public.has_org_permission(organization_id, 'deals.edit'))
  with check (public.has_org_permission(organization_id, 'deals.edit'));

drop policy if exists organization_settings_select on public.organization_settings;
drop policy if exists organization_settings_write on public.organization_settings;
create policy organization_settings_all on public.organization_settings
  for all to authenticated
  using (public.has_org_permission(organization_id, 'settings.manage'))
  with check (public.has_org_permission(organization_id, 'settings.manage'));

drop policy if exists organization_members_select on public.organization_members;
drop policy if exists organization_members_manage on public.organization_members;
create policy organization_members_select on public.organization_members
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and (
      public.has_org_permission(organization_id, 'users.manage')
      or user_id = auth.uid()
    )
  );
create policy organization_members_manage on public.organization_members
  for all to authenticated
  using (public.has_org_permission(organization_id, 'users.manage'))
  with check (public.has_org_permission(organization_id, 'users.manage'));

drop policy if exists organizations_update_manage on public.organizations;
create policy organizations_update_manage on public.organizations
  for update to authenticated
  using (public.has_org_permission(id, 'settings.manage'))
  with check (public.has_org_permission(id, 'settings.manage'));

drop policy if exists audit_logs_select on public.audit_logs;
create policy audit_logs_select on public.audit_logs
  for select to authenticated
  using (
    public.is_org_member(organization_id)
    and (
      public.has_org_permission(organization_id, 'users.manage')
      or public.has_org_permission(organization_id, 'settings.manage')
    )
  );

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type Database = {
  public: {
    Tables: {
      organizations: {
        Row: {
          id: string;
          name: string;
          slug: string;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          slug: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Database["public"]["Tables"]["organizations"]["Insert"]>;
        Relationships: [];
      };
      profiles: {
        Row: {
          id: string;
          email: string;
          full_name: string;
          current_organization_id: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          email: string;
          full_name?: string;
          current_organization_id?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["profiles"]["Insert"]>;
        Relationships: [];
      };
      organization_members: {
        Row: {
          id: string;
          organization_id: string;
          user_id: string;
          role_id: string;
          status: string;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          user_id: string;
          role_id: string;
          status?: string;
        };
        Update: Partial<Database["public"]["Tables"]["organization_members"]["Insert"]>;
        Relationships: [];
      };
      roles: {
        Row: {
          id: string;
          organization_id: string | null;
          key: string;
          name: string;
          description: string;
          is_system: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          organization_id?: string | null;
          key: string;
          name: string;
          description?: string;
          is_system?: boolean;
        };
        Update: Partial<Database["public"]["Tables"]["roles"]["Insert"]>;
        Relationships: [];
      };
      permissions: {
        Row: {
          id: string;
          key: string;
          name: string;
          description: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          key: string;
          name: string;
          description?: string;
        };
        Update: Partial<Database["public"]["Tables"]["permissions"]["Insert"]>;
        Relationships: [];
      };
      role_permissions: {
        Row: {
          role_id: string;
          permission_id: string;
          organization_id: string | null;
        };
        Insert: {
          role_id: string;
          permission_id: string;
          organization_id?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["role_permissions"]["Insert"]>;
        Relationships: [];
      };
      organization_settings: {
        Row: {
          id: string;
          organization_id: string;
          assignor_name: string;
          default_assignment_fee: number;
          default_emd: number;
          notify_phone: string;
          timezone: string;
          branding: Json;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          assignor_name?: string;
          default_assignment_fee?: number;
          default_emd?: number;
          notify_phone?: string;
          timezone?: string;
          branding?: Json;
        };
        Update: Partial<Database["public"]["Tables"]["organization_settings"]["Insert"]>;
        Relationships: [];
      };
      contacts: {
        Row: {
          id: string;
          organization_id: string;
          kind: string;
          full_name: string;
          email: string;
          phone: string;
          company_name: string;
          notes: string;
          metadata: Json;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          kind?: string;
          full_name?: string;
          email?: string;
          phone?: string;
          company_name?: string;
          notes?: string;
          metadata?: Json;
          created_by?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["contacts"]["Insert"]>;
        Relationships: [];
      };
      leads: {
        Row: {
          id: string;
          organization_id: string;
          contact_id: string | null;
          address: string;
          zip_code: string;
          arv: number;
          mao: number;
          wholesale_fee: number;
          risk_level: string;
          flood_risk: boolean;
          status: string;
          seller_name: string;
          seller_phone: string;
          last_contacted: string | null;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          contact_id?: string | null;
          address: string;
          zip_code?: string;
          arv?: number;
          mao?: number;
          wholesale_fee?: number;
          risk_level?: string;
          flood_risk?: boolean;
          status?: string;
          seller_name?: string;
          seller_phone?: string;
          last_contacted?: string | null;
          created_by?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["leads"]["Insert"]>;
        Relationships: [];
      };
      deals: {
        Row: {
          id: string;
          organization_id: string;
          lead_id: string | null;
          contact_id: string | null;
          address: string;
          price: number;
          seller_name: string;
          seller_phone: string;
          buyer_name: string;
          status: string;
          signature: string;
          signed_at: string | null;
          emd: number;
          closing_date: string;
          deal_kind: string;
          assignment_fee: number;
          assignee_email: string;
          sign_token: string;
          emd_paid: boolean;
          stripe_session_id: string;
          notes: string;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          lead_id?: string | null;
          contact_id?: string | null;
          address: string;
          price?: number;
          seller_name?: string;
          seller_phone?: string;
          buyer_name?: string;
          status?: string;
          signature?: string;
          signed_at?: string | null;
          emd?: number;
          closing_date?: string;
          deal_kind?: string;
          assignment_fee?: number;
          assignee_email?: string;
          sign_token?: string;
          emd_paid?: boolean;
          stripe_session_id?: string;
          notes?: string;
          created_by?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["deals"]["Insert"]>;
        Relationships: [];
      };
      files: {
        Row: {
          id: string;
          organization_id: string;
          deal_id: string | null;
          lead_id: string | null;
          contact_id: string | null;
          storage_path: string;
          file_name: string;
          content_type: string;
          byte_size: number;
          kind: string;
          created_by: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          deal_id?: string | null;
          lead_id?: string | null;
          contact_id?: string | null;
          storage_path: string;
          file_name: string;
          content_type?: string;
          byte_size?: number;
          kind?: string;
          created_by?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["files"]["Insert"]>;
        Relationships: [];
      };
      offer_queue: {
        Row: {
          id: string;
          organization_id: string;
          lead_id: string | null;
          deal_id: string | null;
          address: string;
          phone: string;
          seller_name: string;
          offer_price: number;
          sms_preview: string;
          status: string;
          error: string;
          created_at: string;
          sent_at: string | null;
        };
        Insert: {
          id?: string;
          organization_id: string;
          lead_id?: string | null;
          deal_id?: string | null;
          address?: string;
          phone?: string;
          seller_name?: string;
          offer_price?: number;
          sms_preview?: string;
          status?: string;
          error?: string;
          sent_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["offer_queue"]["Insert"]>;
        Relationships: [];
      };
      audit_logs: {
        Row: {
          id: string;
          organization_id: string;
          actor_user_id: string | null;
          action: string;
          entity_type: string;
          entity_id: string;
          meta: Json;
          created_at: string;
        };
        Insert: {
          id?: string;
          organization_id: string;
          actor_user_id?: string | null;
          action: string;
          entity_type?: string;
          entity_id?: string;
          meta?: Json;
        };
        Update: Partial<Database["public"]["Tables"]["audit_logs"]["Insert"]>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: {
      is_org_member: { Args: { target_org: string }; Returns: boolean };
      user_organization_ids: { Args: Record<string, never>; Returns: string[] };
      current_organization_id: { Args: Record<string, never>; Returns: string };
      has_org_permission: {
        Args: { target_org: string; permission_key: string };
        Returns: boolean;
      };
    };
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};

export type ServerOsType = "linux" | "windows";

export interface Server {
  id: string;
  tenant_id: string;
  name: string;
  host: string;
  ssh_port: number;
  os_type: ServerOsType;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServerCreate {
  name: string;
  host: string;
  ssh_port?: number;
  os_type?: ServerOsType;
  description?: string;
  credentials: {
    username: string;
    password?: string;
    private_key?: string;
  };
  is_active?: boolean;
}

export interface ServerUpdate {
  name?: string;
  host?: string;
  ssh_port?: number;
  os_type?: ServerOsType;
  description?: string;
  credentials?: {
    username: string;
    password?: string;
    private_key?: string;
  };
  is_active?: boolean;
}

export interface AnalyzeRequest {
  question: string;
  server_ids: string[];
  integration_ids: string[];
  host_filter?: string;
}

export interface AnalyzeResponse {
  answer: string;
  sources_used: string[];
}

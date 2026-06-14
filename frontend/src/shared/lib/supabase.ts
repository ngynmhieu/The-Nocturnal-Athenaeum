import { createClient } from "@supabase/supabase-js";
import { env } from "@/shared/config";

export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey);

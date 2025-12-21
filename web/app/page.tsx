import { supabase } from '@/utils/supabase/client'
import Dashboard from '@/components/Dashboard'

export const revalidate = 60 // Refresh every minute

export default async function Home() {
  const { data: articles, error } = await supabase
    .from('articles')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(200)

  if (error) {
    return (
      <div className="p-8 text-red-500 bg-red-50 rounded-lg m-8">
        <h2 className="font-bold mb-2">Supabase Connection Error</h2>
        <p>{error.message}</p>
        <p className="mt-2 text-xs opacity-70">Check your URL and API Key in web/.env.local</p>
      </div>
    )
  }

  return <Dashboard initialArticles={articles || []} />
}

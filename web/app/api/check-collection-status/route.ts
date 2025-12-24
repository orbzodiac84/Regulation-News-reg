import { NextResponse } from 'next/server'

export async function GET() {
    try {
        const githubToken = process.env.GITHUB_TOKEN

        if (!githubToken) {
            return NextResponse.json({ error: 'GitHub token not configured' }, { status: 500 })
        }

        // Get the latest run of the specific workflow
        const response = await fetch(
            'https://api.github.com/repos/orbzodiac84/Regulation-News-reg/actions/workflows/news_collector.yml/runs?per_page=1',
            {
                headers: {
                    'Accept': 'application/vnd.github.v3+json',
                    'Authorization': `Bearer ${githubToken}`,
                },
                next: { revalidate: 0 } // Disable caching
            }
        )

        const data = await response.json()

        if (data.workflow_runs && data.workflow_runs.length > 0) {
            const latestRun = data.workflow_runs[0]
            return NextResponse.json({
                status: latestRun.status, // in_progress, completed, queued
                conclusion: latestRun.conclusion, // success, failure, neutral, cancelled, skipped, timed_out, action_required
                url: latestRun.html_url
            })
        }

        return NextResponse.json({ status: 'unknown' })
    } catch (error) {
        console.error('Check status error:', error)
        return NextResponse.json({ error: 'Failed to check status' }, { status: 500 })
    }
}

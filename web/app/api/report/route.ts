
import { GoogleGenerativeAI } from '@google/generative-ai'
import { createClient } from '@supabase/supabase-js'
import { NextResponse } from 'next/server'

// Initialize Supabase
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
const supabase = createClient(supabaseUrl, supabaseKey)

// Initialize Gemini
const apiKey = process.env.GEMINI_API_KEY
if (!apiKey) {
    console.error("❌ GEMINI_API_KEY is missing in environment variables!")
}
const genAI = new GoogleGenerativeAI(apiKey || '')

export async function POST(req: Request) {
    try {
        if (!apiKey) {
            return NextResponse.json({ error: 'Server Misconfiguration: API Key missing' }, { status: 500 })
        }

        const { articleId, title, content, agency } = await req.json()

        if (!articleId) {
            return NextResponse.json({ error: 'Article ID required' }, { status: 400 })
        }

        // 1. Check if report already exists in DB
        const { data: existingData, error: fetchError } = await supabase
            .from('articles')
            .select('analysis_result')
            .eq('id', articleId)
            .single()

        if (fetchError) {
            console.error("DB Fetch Error:", fetchError)
        }

        const existingAnalysis = existingData?.analysis_result || {}

        // If report exists, return it immediately
        if (existingAnalysis.detailed_report) {
            console.log("Returning cached report for", articleId)
            return NextResponse.json({ report: existingAnalysis.detailed_report })
        }

        // 2. Generate Report with Gemini
        console.log("Generating new report for", articleId)
        // Using "gemini-3-flash-preview" as requested for high-quality report generation
        const model = genAI.getGenerativeModel({ model: "gemini-3-flash-preview" })

        const prompt = `
        Role: You are a Chief Risk Officer (CRO) at a major commercial bank in Korea.
        Task: Write a professional executive summary and risk analysis report.
        
        Input:
        - Agency: ${agency}
        - Title: ${title}
        - Content: ${content.substring(0, 5000)}

        Requirements for Style (Critical):
        1. **Strict "Gaejo-style" (개조식) required**: End sentences with nouns or noun-forms (e.g., "예상됨", "필요함", "확인", "불가피"). Do NOT use "것입니다", "합니다", "있습니다".
        2. **Clean Formatting**: Use standard Markdown headers (##, ###). Do NOT use bolding within headers (e.g., use "## Header", not "## **Header**").
        3. **Tone**: Cold, analytical, and concise.

        Structure:
        1. **Executive Summary** (3 lines max, key impact focus)
        2. **Key Regulation Changes** (Bulleted list of facts)
        3. **Market Implications** (Analysis of impact on the banking sector)
        4. **Risk Assessment** (Credit/Market/Operational/Reputational)
        5. **Strategic Recommendations** (Actionable items)

        Output Format:
        Return ONLY the Markdown content.
        `

        const result = await model.generateContent(prompt)
        const response = await result.response
        const reportMarkdown = response.text()

        // 3. Save to DB (Merge with existing analysis_result)
        const updatedAnalysis = {
            ...existingAnalysis,
            detailed_report: reportMarkdown,
            report_generated_at: new Date().toISOString()
        }

        const { error: updateError } = await supabase
            .from('articles')
            .update({ analysis_result: updatedAnalysis })
            .eq('id', articleId)

        if (updateError) {
            console.error("Failed to save report:", updateError)
            // We still return the generated report even if save failed
        }

        return NextResponse.json({ report: reportMarkdown })

    } catch (error) {
        console.error("API Error:", error)
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 })
    }
}

'use client'

import { useState, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'

// --- Interfaces ---
interface Article {
    id: number
    title: string
    link: string
    agency: string
    published_at: string
    analysis_result?: AnalysisResult
    content?: string // Added for report generation
}

interface AnalysisResult {
    summary: string[]
    impact_analysis: string
    risk_level: string
    importance_score: number
    keywords: string[]
    risk_tags?: string[]
}

// --- Icons ---
const Icons = {
    Home: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
    ),
    List: () => (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
    ),
    Timeline: () => (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    ),
    ChevronDown: () => (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
    ),
    ChevronUp: () => (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
    ),
    Sparkles: () => (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 3.214L13 21l-2.286-6.857L5 12l5.714-3.214L13 3z" />
        </svg>
    )
}

import ReportModal from './ReportModal'

interface DashboardProps {
    initialArticles?: Article[]
}

export default function Dashboard({ initialArticles = [] }: DashboardProps) {
    const [articles, setArticles] = useState<Article[]>(initialArticles)
    const [selectedAgency, setSelectedAgency] = useState('All')
    const [selectedRisk, setSelectedRisk] = useState('All')
    const [loading, setLoading] = useState(initialArticles.length === 0)
    const [viewMode, setViewMode] = useState<'list' | 'timeline'>('timeline') // Default to Timeline

    // Timeline View State: Expanded dates (Initially Empty = All Collapsed)
    const [expandedDates, setExpandedDates] = useState<{ [key: string]: boolean }>({})

    // Report Modal State
    const [isReportOpen, setIsReportOpen] = useState(false)
    const [selectedReportArticle, setSelectedReportArticle] = useState<Article | null>(null)

    const handleOpenReport = (article: Article) => {
        setSelectedReportArticle(article)
        setIsReportOpen(true)
    }

    // Config
    const supabase = createClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    )

    // Data Fetching
    useEffect(() => {
        fetchArticles(selectedAgency)

        const subscription = supabase
            .channel('articles-channel')
            .on(
                'postgres_changes',
                { event: 'INSERT', schema: 'public', table: 'articles' },
                () => {
                    fetchArticles(selectedAgency)
                }
            )
            .subscribe()

        return () => {
            subscription.unsubscribe()
        }
    }, [selectedAgency])

    const fetchArticles = async (agency: string = 'All') => {
        setLoading(true)
        let query = supabase
            .from('articles')
            .select('*')
            .order('published_at', { ascending: false })
            .limit(1000)

        if (agency !== 'All') {
            query = query.eq('agency', agency)
        }

        const { data, error } = await query

        if (error) console.error('Error:', error)
        else {
            setArticles(data || [])
            // Removed auto-expansion logic to keep all collapsed by default
        }
        setLoading(false)
    }

    // Helper Functions
    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr)
        const month = date.getUTCMonth() + 1
        const day = date.getUTCDate()
        const hour = date.getUTCHours()
        const minute = date.getUTCMinutes()

        if (hour === 0 && minute === 0) {
            return `${month}월 ${day}일`
        }
        return `${month}월 ${day}일 ${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`
    }

    const getDateDateString = (dateStr: string) => {
        const date = new Date(dateStr)
        const year = date.getUTCFullYear()
        const month = date.getUTCMonth() + 1
        const day = date.getUTCDate()
        const weekDays = ['일', '월', '화', '수', '목', '금', '토']
        const weekDay = weekDays[date.getUTCDay()]
        return `${year}. ${month}. ${day} (${weekDay})`
    }

    const getRiskColor = (risk: string) => {
        switch (risk?.toUpperCase()) {
            case 'HIGH': return 'text-red-600 bg-red-50 border-red-100'
            case 'MEDIUM': return 'text-amber-600 bg-amber-50 border-amber-100'
            default: return 'text-emerald-600 bg-emerald-50 border-emerald-100'
        }
    }

    const getAgencyColor = (agency: string) => {
        switch (agency) {
            case 'FSC': return 'bg-sky-100 text-sky-700'
            case 'FSS': return 'bg-blue-100 text-blue-700'
            case 'MOEF': return 'bg-slate-100 text-slate-700'
            case 'BOK': return 'bg-indigo-100 text-indigo-700'
            default: return 'bg-gray-100 text-gray-700'
        }
    }

    // Display Names Mapping
    const agencyDisplayNames: { [key: string]: string } = {
        'All': '전체 보기',
        'MOEF': '기획재정부',
        'FSC': '금융위원회',
        'FSS': '금융감독원',
        'BOK': '한국은행'
    }

    const agencies = ['All', 'FSC', 'FSS', 'MOEF', 'BOK']

    // Filter Logic
    const filteredAndSortedArticles = articles
        .filter(article => {
            if (selectedAgency !== 'All' && article.agency !== selectedAgency) return false

            const risk = article.analysis_result?.risk_level || 'Low'
            const hasAnalysis = article.analysis_result && article.analysis_result.summary && article.analysis_result.summary.length > 0

            if (!hasAnalysis) return false
            if (risk === 'Low' && selectedRisk !== 'Low') return false
            if (selectedRisk !== 'All' && risk.toUpperCase() !== selectedRisk.toUpperCase()) return false

            return true
        })

    // Grouping for Timeline View
    const groupedArticles: { [key: string]: Article[] } = {}
    filteredAndSortedArticles.forEach(article => {
        const dateKey = getDateDateString(article.published_at)
        if (!groupedArticles[dateKey]) {
            groupedArticles[dateKey] = []
        }
        groupedArticles[dateKey].push(article)
    })

    // Convert to array of [date, articles] for rendering, preserving sort order
    // Since filteredAndSortedArticles is already sorted by date desc, 
    // we can iterate through it to build the ordered keys.
    const orderedDateKeys: string[] = []
    const seenDates = new Set<string>()
    filteredAndSortedArticles.forEach(article => {
        const dateKey = getDateDateString(article.published_at)
        if (!seenDates.has(dateKey)) {
            seenDates.add(dateKey)
            orderedDateKeys.push(dateKey)
        }
    })

    const toggleDateExpansion = (date: string) => {
        setExpandedDates(prev => ({
            ...prev,
            [date]: !prev[date]
        }))
    }

    // --- Sub-Components (Clean Code) ---

    // 1. Article Card (Reused in both views)
    const ArticleCard = ({ article }: { article: Article }) => {
        const analysis = article.analysis_result
        const risk = analysis?.risk_level || 'Low'

        return (
            <div className="group relative bg-white rounded-2xl border border-slate-200 overflow-hidden hover:border-sky-200 hover:shadow-md hover:shadow-sky-100/50 transition-all duration-300 mb-6 last:mb-0">
                <div className="px-6 py-5">
                    {/* Meta */}
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                            <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide ${getAgencyColor(article.agency)}`}>
                                {agencyDisplayNames[article.agency] || article.agency}
                            </span>
                            <span className="text-sm text-slate-400 font-medium">
                                {formatDate(article.published_at)}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            {/* Risk Tags */}
                            {analysis?.risk_tags && analysis.risk_tags.map(tag => (
                                <span key={tag} className="px-2 py-0.5 rounded-md text-[10px] font-bold text-sky-600 bg-sky-50 border border-sky-100">
                                    {tag}
                                </span>
                            ))}
                            {/* Grade */}
                            {risk !== 'Low' && (
                                <div className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border ${getRiskColor(risk)}`}>
                                    {risk}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Title & Action */}
                    <div className="flex items-start justify-between gap-4">
                        <h3 className="text-lg font-bold text-slate-900 leading-snug group-hover:text-sky-600 transition-colors flex-1">
                            <a href={article.link} target="_blank" rel="noopener noreferrer" className="block outline-none">
                                {article.title}
                            </a>
                        </h3>

                        {/* Report Button (Prominent) */}
                        <button
                            onClick={() => handleOpenReport(article)}
                            className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white rounded-lg text-xs font-bold shadow-sm shadow-sky-200 hover:shadow-md transition-all transform hover:-translate-y-0.5"
                            title="AI 심층 리포트 생성"
                        >
                            <Icons.Sparkles />
                            <span className="hidden sm:inline">AI 심층분석</span>
                        </button>
                    </div>
                </div >

                {/* Analysis Body */}
                {
                    analysis && (analysis.summary?.length > 0 || analysis.impact_analysis) && (
                        <div className="px-6 pb-6 pt-0 space-y-3">
                            {analysis.summary && analysis.summary.length > 0 && (
                                <div className="bg-sky-50/30 rounded-xl p-4 border border-sky-100/50 group-hover:bg-sky-50/60 group-hover:border-sky-100 transition-colors">
                                    <h4 className="text-xs font-bold text-sky-600 uppercase mb-3 flex items-center gap-1.5 tracking-wider">Key Points</h4>
                                    <ul className="space-y-2">
                                        {analysis.summary.map((point, idx) => (
                                            <li key={idx} className="text-[15px] text-slate-800 pl-3 relative leading-relaxed">
                                                <span className="absolute left-0 top-2.5 w-1 h-1 bg-slate-400 rounded-full"></span>
                                                {point}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {analysis.impact_analysis && (
                                <div className="bg-sky-50/30 rounded-xl p-4 border border-sky-100/50 group-hover:bg-sky-50/60 group-hover:border-sky-100 transition-colors">
                                    <h4 className="text-xs font-bold text-sky-600 uppercase mb-3 flex items-center gap-1.5 tracking-wider">Banking Impact</h4>
                                    <p className="text-[15px] text-slate-800 leading-relaxed">{analysis.impact_analysis}</p>
                                </div>
                            )}
                        </div>
                    )
                }
            </div >
        )
    }

    return (
        <div className="min-h-screen bg-white font-sans text-slate-900">
            {/* Header */}
            <header className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8">
                <div className="flex items-center gap-3">
                    <div className="bg-sky-500 rounded-lg p-1.5 text-white shadow-sm shadow-sky-200">
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375h-2.169c.86.671 1.419 1.71 1.419 2.89 0 2.002-1.624 3.625-3.625 3.625a3.618 3.618 0 0 0-.75-.078v4.938c0 .621.504 1.125 1.125 1.125H9.75a1.125 1.125 0 0 1 1.125 1.125v1.5a3.375 3.375 0 0 0 3.375 3.375h2.17c-.861-.672-1.42-1.711-1.42-2.891 0-2.002 1.623-3.625 3.625-3.625.255 0 .502.027.749.079Z" />
                        </svg>
                    </div>
                    <h1 className="text-lg font-bold tracking-tight text-slate-900">
                        Financial Regulatory Insights
                    </h1>
                </div>
                <div className="flex items-center gap-4">
                    <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-full border border-slate-100">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span className="text-xs font-semibold text-slate-500">Live Updates</span>
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto flex pt-16 min-h-screen">
                {/* Left Sidebar */}
                <aside className="hidden md:block w-64 fixed h-full border-r border-slate-100 px-4 py-6 overflow-y-auto">
                    <div className="space-y-8">
                        <div>
                            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 px-3 flex items-center gap-2">
                                <Icons.Home /> Sources
                            </h2>
                            <nav className="space-y-1">
                                {agencies.map(agency => (
                                    <button
                                        key={agency}
                                        onClick={() => setSelectedAgency(agency)}
                                        className={`w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium rounded-lg transition-colors ${selectedAgency === agency
                                            ? 'bg-sky-50 text-sky-600'
                                            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                                            }`}
                                    >
                                        <span>{agencyDisplayNames[agency]}</span>
                                        {selectedAgency === agency && (
                                            <div className="w-1.5 h-1.5 rounded-full bg-sky-500" />
                                        )}
                                    </button>
                                ))}
                            </nav>
                        </div>
                    </div>
                </aside>

                {/* Main Content */}
                <main className="flex-1 md:ml-64 p-4 sm:p-6 lg:p-8 max-w-4xl">
                    {/* Mobile Filters */}
                    <div className="md:hidden overflow-x-auto flex gap-2 mb-6 pb-2 scrollbar-hide">
                        {agencies.map(agency => (
                            <button
                                key={agency}
                                onClick={() => setSelectedAgency(agency)}
                                className={`whitespace-nowrap px-4 py-2 rounded-full text-sm font-medium transition-colors border ${selectedAgency === agency
                                    ? 'bg-sky-500 text-white border-sky-500 shadow-sm'
                                    : 'bg-white text-slate-600 border-slate-200'
                                    }`}
                            >
                                {agencyDisplayNames[agency]}
                            </button>
                        ))}
                    </div>

                    {/* Content Header: Refresh & View Switcher - Sticky */}
                    <div className="sticky top-16 z-30 bg-white/95 backdrop-blur-sm pb-4 mb-2 -mx-4 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 border-b border-slate-100">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-bold text-slate-900">Latest Updates</h2>

                            <div className="flex items-center gap-3">
                                {/* View Switcher */}
                                <div className="flex items-center bg-slate-100 rounded-lg p-1 border border-slate-200">
                                    <button
                                        onClick={() => setViewMode('list')}
                                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${viewMode === 'list' ? 'bg-white text-sky-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                                    >
                                        <Icons.List /> 리스트
                                    </button>
                                    <button
                                        onClick={() => setViewMode('timeline')}
                                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${viewMode === 'timeline' ? 'bg-white text-sky-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                                    >
                                        <Icons.Timeline /> 날짜별
                                    </button>
                                </div>

                                <button
                                    onClick={() => fetchArticles(selectedAgency)}
                                    className="p-2 text-slate-400 hover:text-sky-600 hover:bg-sky-50 rounded-full transition-all"
                                    title="Refresh"
                                >
                                    <svg className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                </button>
                            </div>
                        </div>

                        {/* Risk Filter Chips */}
                        <div className="flex flex-wrap gap-2">
                            {['All', 'High', 'Medium', 'Low'].map(risk => (
                                <button
                                    key={risk}
                                    onClick={() => setSelectedRisk(risk)}
                                    className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide transition-all duration-200 border ${selectedRisk === risk
                                        ? 'bg-sky-500 text-white border-sky-500 shadow-sm shadow-sky-200'
                                        : 'bg-white text-slate-500 border-slate-200 hover:border-slate-300 hover:text-slate-700 hover:bg-slate-50'
                                        }`}
                                >
                                    {risk === 'All' ? 'Every Level' : `${risk} Risk`}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Articles - Render based on View Mode */}
                    <div className="space-y-6">
                        {loading && articles.length === 0 ? (
                            <div className="space-y-4 animate-pulse">
                                {[1, 2, 3].map(i => (
                                    <div key={i} className="h-48 bg-slate-50 rounded-2xl border border-slate-100"></div>
                                ))}
                            </div>
                        ) : (
                            viewMode === 'list' ? (
                                // --- List View (Default) ---
                                // Just simple list 
                                filteredAndSortedArticles.map((article) => (
                                    <ArticleCard key={article.id} article={article} />
                                ))
                            ) : (
                                // --- Timeline View (Grouped by Date) ---
                                <div className="space-y-6">
                                    {orderedDateKeys.map((date, index) => {
                                        const isExpanded = expandedDates[date]
                                        const dateArticles = groupedArticles[date]
                                        const isLatest = index === 0

                                        return (
                                            <div key={date} className="bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow-md transition-all duration-200">
                                                {/* Date Header Accordion Trigger - Sticky when expanded */}
                                                <button
                                                    onClick={() => toggleDateExpansion(date)}
                                                    className={`w-full flex items-center justify-between px-6 py-4 transition-colors ${isExpanded ? 'sticky top-36 z-20 bg-white/95 backdrop-blur-sm border-b border-sky-100 shadow-sm' : 'hover:bg-slate-50'}`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <span className={`w-1 h-5 rounded-full ${isLatest ? 'bg-sky-500' : 'bg-slate-300'}`}></span>
                                                        <h3 className={`text-base font-bold ${isLatest ? 'text-sky-900' : 'text-slate-700'}`}>
                                                            {date}
                                                        </h3>

                                                        {/* Stats Badge */}
                                                        <div className="flex items-center gap-2 ml-2">
                                                            <span className="px-2.5 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-600">
                                                                총 {dateArticles.length}건
                                                            </span>
                                                            {/* Minimal Agency Stats Breakdown (Full Name) */}
                                                            <div className="hidden sm:flex items-center gap-1.5 text-[11px] text-slate-400 font-medium">
                                                                {['FSS', 'FSC', 'BOK', 'MOEF'].map(ag => {
                                                                    const count = dateArticles.filter(a => a.agency === ag).length
                                                                    if (count === 0) return null
                                                                    const colorClass = ag === 'FSS' ? 'text-blue-600 bg-blue-50'
                                                                        : ag === 'FSC' ? 'text-sky-600 bg-sky-50'
                                                                            : ag === 'BOK' ? 'text-indigo-600 bg-indigo-50'
                                                                                : 'text-slate-600 bg-slate-100' // MOEF

                                                                    const name = agencyDisplayNames[ag] || ag // Use Full Name
                                                                    return (
                                                                        <span key={ag} className={`px-1.5 py-0.5 rounded ${colorClass}`}>
                                                                            {name} {count}
                                                                        </span>
                                                                    )
                                                                })}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="text-slate-400">
                                                        {isExpanded ? <Icons.ChevronUp /> : <Icons.ChevronDown />}
                                                    </div>
                                                </button>

                                                {/* Collapsible Content */}
                                                {isExpanded && (
                                                    <div className="divide-y divide-slate-100 bg-slate-50/30">
                                                        {dateArticles.sort((a, b) => {
                                                            // 1. Risk Level (High > Medium > Low)
                                                            const riskOrder: { [key: string]: number } = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 }
                                                            const riskA = riskOrder[a.analysis_result?.risk_level?.toUpperCase() || 'LOW'] || 0
                                                            const riskB = riskOrder[b.analysis_result?.risk_level?.toUpperCase() || 'LOW'] || 0
                                                            if (riskA !== riskB) return riskB - riskA // Descending

                                                            // 2. Agency Priority (FSS > FSC > MOEF > BOK)
                                                            const agencyOrder: { [key: string]: number } = { 'FSS': 1, 'FSC': 2, 'MOEF': 3, 'BOK': 4 }
                                                            const agA = agencyOrder[a.agency] || 99
                                                            const agB = agencyOrder[b.agency] || 99

                                                            return agA - agB // Ascending (1 is top)
                                                        }).map(article => (
                                                            <div key={article.id} className="p-4 sm:p-6">
                                                                <ArticleCard article={article} />
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            )
                        )}
                    </div>
                </main>
            </div>

            <ReportModal
                isOpen={isReportOpen}
                onClose={() => setIsReportOpen(false)}
                article={selectedReportArticle}
            />
        </div>
    )
}

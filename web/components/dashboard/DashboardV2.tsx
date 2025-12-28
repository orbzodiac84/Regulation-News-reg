
'use client'

import React, { useEffect, useState, useMemo } from 'react'
import { toKSTDate } from '@/utils/date' // Use new utils
import { supabase } from '@/utils/supabase/client'
import Header from './Header'
import SearchBar from './SearchBar'
import DateSection from './DateSection'
import ReportModal from '@/components/ReportModal' // Reuse existing modal
import { Article } from './NewsCard'

export default function DashboardV2() {
    const [articles, setArticles] = useState<Article[]>([])
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')

    // Modal State
    const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
    const [isReportModalOpen, setIsReportModalOpen] = useState(false)
    const [isMenuOpen, setIsMenuOpen] = useState(false) // Sidebar toggle

    // 1. Fetch Data
    useEffect(() => {
        fetchArticles()
    }, [])

    const fetchArticles = async () => {
        setLoading(true)
        const { data, error } = await supabase
            .from('articles')
            .select('*')
            .order('published_at', { ascending: false })
            .limit(1000)

        if (error) {
            console.error('Error fetching articles:', error)
        } else {
            setArticles(data || [])
        }
        setLoading(false)
    }

    // 2. Filter & Group Data
    const processedData = useMemo(() => {
        // A. Filter by Search Query
        let filtered = articles
        if (searchQuery) {
            const lowerQ = searchQuery.toLowerCase()
            filtered = filtered.filter(a =>
                a.title.toLowerCase().includes(lowerQ) ||
                (a.analysis_result?.keywords || []).some((k: string) => k.toLowerCase().includes(lowerQ))
            )
        }

        // B. Group by Date
        const grouped: Record<string, Article[]> = {}
        filtered.forEach(article => {
            const kstDate = toKSTDate(article.published_at)
            const dateKey = `${kstDate.getUTCFullYear()}. ${kstDate.getUTCMonth() + 1}. ${kstDate.getUTCDate()}`

            // Add Day of Week
            const weekDays = ['일', '월', '화', '수', '목', '금', '토']
            const fullDateTitle = `${dateKey} (${weekDays[kstDate.getUTCDay()]})`

            if (!grouped[fullDateTitle]) grouped[fullDateTitle] = []
            grouped[fullDateTitle].push(article)
        })

        return grouped
    }, [articles, searchQuery])

    // 3. Handlers
    const handleGenerateReport = (article: Article) => {
        setSelectedArticle(article)
        setIsReportModalOpen(true)
    }

    // Sidebar Content (StockEasy Style: Dark Theme)
    const Sidebar = () => (
        <>
            {/* Backdrop */}
            {isMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/60 z-50 transition-opacity duration-300"
                    onClick={() => setIsMenuOpen(false)}
                />
            )}

            {/* Drawer */}
            <div className={`fixed inset-y-0 left-0 w-[280px] bg-[#1E1E1E] text-white z-[60] transform transition-transform duration-300 shadow-2xl ${isMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
                <div className="p-6 h-full flex flex-col">
                    {/* Brand */}
                    <div className="mb-10 flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-[#5B4BFF] flex items-center justify-center font-bold text-white">R</div>
                        <h2 className="text-xl font-bold tracking-tight">RegBrief</h2>
                    </div>

                    {/* Menu Items */}
                    <nav className="flex-1 space-y-1">
                        <button className="flex items-center gap-3 w-full text-left px-4 py-3 text-gray-300 hover:text-white hover:bg-white/10 rounded-xl transition-all">
                            <span className="font-medium">홈</span>
                        </button>
                        <button className="flex items-center gap-3 w-full text-left px-4 py-3 text-gray-300 hover:text-white hover:bg-white/10 rounded-xl transition-all">
                            <span className="font-medium">스크랩 보관함</span>
                        </button>

                        <div className="my-6 border-t border-white/10"></div>
                        <div className="px-4 text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Agency Filter</div>

                        {['FSC', 'FSS', 'MOEF', 'BOK'].map(agency => (
                            <button key={agency} className="flex items-center gap-3 w-full text-left px-4 py-3 text-gray-300 hover:text-white hover:bg-white/10 rounded-xl transition-all">
                                <span>{agency}</span>
                            </button>
                        ))}
                    </nav>

                    {/* Footer */}
                    <div className="text-xs text-gray-500 mt-auto">
                        v2.0.0 (Beta)
                    </div>
                </div>
            </div>
        </>
    )

    return (
        <div className="min-h-screen bg-[#F5F7FA] text-gray-900 font-sans pb-20 selection:bg-[#5B4BFF]/20">
            <Sidebar />
            <Header onMenuClick={() => setIsMenuOpen(true)} />
            <SearchBar onSearch={setSearchQuery} />

            <main className="max-w-md mx-auto pt-6 px-0 sm:px-4">
                {/* Search Result Header / Reset Button */}
                {searchQuery && (
                    <div className="px-4 mb-4 flex items-center justify-between">
                        <div className="text-sm font-medium text-gray-900">
                            '<span className="text-[#5B4BFF]">{searchQuery}</span>' 검색 결과: {processedData ? Object.values(processedData).flat().length : 0}건
                        </div>
                        <button
                            onClick={() => { setSearchQuery(''); /* Reset input via key or context ideally, but simple reload works */ }}
                            className="text-xs text-gray-500 underline hover:text-gray-800"
                        >
                            전체 목록으로 돌아가기
                        </button>
                    </div>
                )}

                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20 space-y-4">
                        <div className="w-8 h-8 border-4 border-[#5B4BFF]/30 border-t-[#5B4BFF] rounded-full animate-spin"></div>
                        <div className="text-sm text-gray-400 font-medium">데이터를 불러오는 중...</div>
                    </div>
                ) : (
                    Object.entries(processedData).map(([dateTitle, dayArticles]) => (
                        <DateSection
                            key={dateTitle}
                            dateTitle={dateTitle}
                            articles={dayArticles}
                            onGenerateReport={handleGenerateReport}
                        />
                    ))
                )}

                {!loading && Object.keys(processedData).length === 0 && (
                    <div className="flex flex-col items-center justify-center py-20 text-center px-6">
                        <p className="text-lg font-bold text-gray-400 mb-2">검색 결과가 없습니다.</p>
                        <p className="text-sm text-gray-400">다른 키워드로 검색해보세요.</p>
                        <button
                            onClick={() => setSearchQuery('')}
                            className="mt-6 px-6 py-2 bg-white border border-gray-300 rounded-full text-sm font-medium hover:bg-gray-50"
                        >
                            목록 초기화
                        </button>
                    </div>
                )}
            </main>

            {/* Report Modal (Legacy) */}
            {isReportModalOpen && selectedArticle && (
                <ReportModal
                    isOpen={isReportModalOpen}
                    onClose={() => setIsReportModalOpen(false)}
                    article={selectedArticle as any} // Type compatibility cast
                />
            )}
        </div>
    )
}

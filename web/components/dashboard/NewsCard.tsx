
import React, { useState } from 'react'
import { ChevronDown, ChevronUp, FileText, ExternalLink, Sparkles } from 'lucide-react'
import StarRating from './StarRating'

// Type definition (Match DB schema mostly)
export interface Article {
    id: string;
    title: string;
    agency: string;
    published_at: string;
    link: string;
    analysis_result?: {
        summary?: string[];
        importance_score?: number;
        risk_level?: string;
        keywords?: string[]; // Added for search filter
    };
    view_count?: number;
    star_rating?: number; // Manual rating if any
}

interface NewsCardProps {
    article: Article;
    onGenerateReport: (article: Article) => void;
}

export default function NewsCard({ article, onGenerateReport }: NewsCardProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    // Calculate effective score (Manual > AI > Default)
    const score = article.star_rating ?? article.analysis_result?.importance_score ?? 3

    // Badge Color for Agency
    const getAgencyColor = (agency: string) => {
        switch (agency) {
            case 'FSS': return 'bg-blue-100 text-blue-700'
            case 'BOK': return 'bg-purple-100 text-purple-700'
            case 'FSC': return 'bg-green-100 text-green-700'
            case 'MOEF': return 'bg-orange-100 text-orange-700'
            default: return 'bg-gray-100 text-gray-600'
        }
    }

    // Agency Name Mapping (EN -> KR)
    const getAgencyName = (code: string) => {
        const map: Record<string, string> = {
            'FSC': '금융위',
            'FSS': '금감원',
            'MOEF': '기재부',
            'BOK': '한국은행'
        }
        return map[code] || code
    }

    // Time display (HH:mm)
    const timeStr = new Date(article.published_at).toLocaleTimeString('ko-KR', {
        hour: '2-digit', minute: '2-digit', hour12: false
    });

    return (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden transition-all duration-200 active:scale-[0.99] hover:shadow-md">
            {/* Header / Collapsed View */}
            <div
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-4 cursor-pointer"
            >
                <div className="flex justify-between items-start gap-3">
                    <div className="flex-1">
                        {/* Meta: Agency & Time */}
                        <div className="flex items-center gap-2 mb-1.5">
                            <span className={`px-2 py-0.5 text-[11px] font-bold rounded-md ${getAgencyColor(article.agency)}`}>
                                {getAgencyName(article.agency)}
                            </span>
                            <div className="w-0.5 h-2.5 bg-gray-200 rounded-full"></div>
                            <span className="text-xs text-gray-400 font-medium tracking-tight">
                                {timeStr}
                            </span>
                        </div>

                        {/* Title */}
                        <h3 className={`text-[15px] font-bold leading-snug text-gray-900 ${isExpanded ? '' : 'line-clamp-2'}`}>
                            {article.title}
                        </h3>
                    </div>

                    {/* Right: Score & Toggle Icon */}
                    <div className="flex flex-col items-end gap-2 min-w-[60px]">
                        <StarRating score={score} size={12} />
                        {isExpanded ? <ChevronUp size={16} className="text-gray-300" /> : <ChevronDown size={16} className="text-gray-300" />}
                    </div>
                </div>
            </div>

            {/* Expanded Content */}
            {isExpanded && (
                <div className="px-4 pb-4 pt-0 border-t border-gray-50 bg-gray-50/30">
                    <div className="mt-3 space-y-3">
                        {/* AI Summary */}
                        {article.analysis_result?.summary ? (
                            <div className="bg-white p-3 rounded-xl border border-gray-100 text-sm text-gray-600 space-y-1 shadow-sm">
                                <div className="flex items-center gap-1.5 text-xs font-bold text-[#5B4BFF] mb-1">
                                    <Sparkles size={12} />
                                    AI 3줄 요약
                                </div>
                                <ul className="list-disc list-outside pl-4 space-y-1">
                                    {article.analysis_result.summary.map((line, idx) => (
                                        <li key={idx} className="leading-relaxed">{line}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : (
                            <p className="text-sm text-gray-400 italic p-2">AI 요약이 아직 생성되지 않았습니다.</p>
                        )}

                        {/* Actions */}
                        <div className="grid grid-cols-2 gap-2 mt-2">
                            <a
                                href={article.link}
                                target="_blank"
                                rel="noreferrer"
                                className="flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-white border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
                            >
                                <ExternalLink size={16} />
                                원문 보기
                            </a>

                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onGenerateReport(article);
                                }}
                                className="flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-[#5B4BFF] text-white text-sm font-bold shadow-md shadow-blue-500/20 hover:bg-[#4A3AFF] transition-all active:scale-95"
                            >
                                <FileText size={16} />
                                심층 보고서
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

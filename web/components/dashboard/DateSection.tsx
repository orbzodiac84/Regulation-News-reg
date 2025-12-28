
import React from 'react'
import NewsCard, { Article } from './NewsCard'

interface DateSectionProps {
    dateTitle: string;
    articles: Article[];
    onGenerateReport: (article: Article) => void;
}

export default function DateSection({ dateTitle, articles, onGenerateReport }: DateSectionProps) {
    return (
        <section className="mb-6">
            {/* Sticky Date Header */}
            <div className="sticky top-28 z-30 py-2 bg-[#F5F7FA]/95 backdrop-blur-sm mb-2">
                <h2 className="px-4 text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
                    {dateTitle}
                </h2>
            </div>

            {/* Articles List */}
            <div className="px-4 space-y-3">
                {articles.map(article => (
                    <NewsCard
                        key={article.id}
                        article={article}
                        onGenerateReport={onGenerateReport}
                    />
                ))}
            </div>
        </section>
    )
}

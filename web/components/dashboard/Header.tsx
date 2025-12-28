
import React from 'react'
import { Menu, Settings } from 'lucide-react'

interface HeaderProps {
    onMenuClick: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
    return (
        <header className="sticky top-0 z-50 bg-white border-b border-gray-100 shadow-sm h-14 px-4 flex items-center justify-between">
            {/* Left: Menu Button */}
            <button
                onClick={onMenuClick}
                className="p-2 -ml-2 text-gray-600 hover:bg-gray-50 rounded-full transition-colors"
                aria-label="Menu"
            >
                <Menu size={24} />
            </button>

            {/* Center: Brand Logo */}
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
                <span className="text-[#5B4BFF]">Reg</span>Brief
            </h1>

            {/* Right: Settings / Profile (Placeholder) */}
            <button
                className="p-2 -mr-2 text-gray-400 hover:text-gray-600 rounded-full transition-colors"
                aria-label="Settings"
            >
                <Settings size={22} />
            </button>
        </header>
    )
}

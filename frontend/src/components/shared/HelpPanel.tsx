import { useState } from "react";
import { HelpCircle, X } from "lucide-react";

interface HelpSection {
    heading: string;
    content: string;
}

interface HelpPanelProps {
    title: string;
    sections: HelpSection[];
}

export default function HelpPanel({ title, sections }: HelpPanelProps) {
    const [open, setOpen] = useState(false);

    return (
        <>
            <button
                onClick={() => setOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)]"
                aria-label={`Help for ${title}`}
            >
                <HelpCircle className="h-4 w-4" />
                <span className="hidden sm:inline">Help</span>
            </button>

            {open && (
                <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4">
                    <div
                        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
                        onClick={() => setOpen(false)}
                    />
                    <div className="relative w-full max-w-lg rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6 shadow-xl animate-fade-in">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <HelpCircle className="h-5 w-5 text-accent-500" />
                                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                                    {title}
                                </h2>
                            </div>
                            <button
                                onClick={() => setOpen(false)}
                                className="rounded-lg p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)]"
                                aria-label="Close help"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                            {sections.map((section) => (
                                <div key={section.heading}>
                                    <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">
                                        {section.heading}
                                    </h3>
                                    <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
                                        {section.content}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

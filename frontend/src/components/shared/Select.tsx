import { clsx } from "clsx";
import { ChevronDown } from "lucide-react";

interface SelectOption {
    value: string | number;
    label: string;
}

interface SelectProps {
    label?: string;
    options: SelectOption[];
    value: string | number | undefined;
    onChange: (value: string) => void;
    placeholder?: string;
    className?: string;
    disabled?: boolean;
}

export default function Select({
    label,
    options,
    value,
    onChange,
    placeholder = "Select...",
    className,
    disabled = false,
}: SelectProps) {
    return (
        <div className={clsx("flex flex-col gap-1.5", className)}>
            {label && (
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                    {label}
                </label>
            )}
            <div className="relative">
                <select
                    value={value ?? ""}
                    onChange={(e) => onChange(e.target.value)}
                    disabled={disabled}
                    className={clsx(
                        "w-full appearance-none rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 pr-8 text-sm text-[var(--text-primary)]",
                        "focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "transition-colors"
                    )}
                >
                    <option value="" disabled>
                        {placeholder}
                    </option>
                    {options.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                            {opt.label}
                        </option>
                    ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
            </div>
        </div>
    );
}

interface DisclaimerBannerProps {
    className?: string;
}

export default function DisclaimerBanner({ className }: DisclaimerBannerProps) {
    return (
        <div
            className={`rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 ${className ?? ""}`}
        >
            <p className="text-xs text-amber-600 dark:text-amber-400">
                <strong>Disclaimer:</strong> All predictions, simulations, and statistical outputs are
                for <strong>educational and entertainment purposes only</strong>. They do not
                constitute gambling advice or betting recommendations. Never gamble based on these
                results.{" "}
                <a
                    href="https://github.com/your-username/MatchMind/blob/main/TERMS_OF_SERVICE.md"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-amber-700 dark:hover:text-amber-300"
                >
                    Terms of Service
                </a>
            </p>
        </div>
    );
}

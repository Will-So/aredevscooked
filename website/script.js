// Load and display metrics from metrics_latest.json
(function() {
    'use strict';

    // Configuration
    const METRICS_URL = 'metrics_latest.json';

    // Utility functions
    function formatNumber(num) {
        return new Intl.NumberFormat('en-US').format(num);
    }

    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short'
        });
    }

    function formatPercentage(pct) {
        const sign = pct > 0 ? '+' : '';
        return `${sign}${pct.toFixed(2)}%`;
    }

    function getChangeClass(value) {
        if (value > 0) return 'positive';
        if (value < 0) return 'negative';
        return 'neutral';
    }

    const MATRIX_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*<>[]{}|/\\';

    function matrixReveal(element, finalText, duration) {
        duration = duration || 1800;
        const len = finalText.length;
        const lockInterval = duration / (len + 1);
        let locked = 0;
        let frame;

        function scramble() {
            let display = '';
            for (let i = 0; i < len; i++) {
                if (i < locked) {
                    display += finalText[i];
                } else if (finalText[i] === ' ') {
                    display += ' ';
                } else {
                    display += MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
                }
            }
            element.textContent = display;
            if (locked <= len) {
                frame = requestAnimationFrame(scramble);
            }
        }

        scramble();

        const lockTimer = setInterval(function () {
            locked++;
            if (locked > len) {
                clearInterval(lockTimer);
                cancelAnimationFrame(frame);
                element.textContent = finalText;
            }
        }, lockInterval);
    }

    function getBadgeHTML(badge) {
        return `<span class="badge badge-${badge}">${badge.replace(/_/g, ' ')}</span>`;
    }

    // Render functions
    function renderAggregateBadge(elementId, badge, summaryText = null) {
        const element = document.getElementById(elementId);
        if (element) {
            let html = getBadgeHTML(badge);
            if (summaryText) {
                html += `<br><span class="summary-text" style="margin-top: 0.5rem; display: inline-block; color: var(--text-secondary); font-size: 0.9rem;">${summaryText}</span>`;
            }
            element.innerHTML = html;
        }
    }

    function renderHeadcountCompany(companyName, data) {
        const current = formatNumber(data.current);
        const dataDate = data.data_date ? `as of ${data.data_date}` : '';
        const sourceUrls = data.source_urls || [];

        let changesHTML = '';
        if (data.changes && Object.keys(data.changes).length > 0) {
            changesHTML = '<div class="company-changes">';
            for (const [period, change] of Object.entries(data.changes)) {
                const periodLabel = period.replace(/_/g, ' ').replace('ago', '');

                // Check if data is available
                if (change.value === null || change.pct === null) {
                    changesHTML += `
                        <div class="change-item">
                            <span class="change-label">${periodLabel}</span>
                            <span class="change-value" style="color: #6b7280;">N/A</span>
                            <span class="badge badge-neutral" style="font-size: 0.7rem; padding: 0.25rem 0.5rem; opacity: 0.5;">no data</span>
                        </div>
                    `;
                } else {
                    const valueClass = getChangeClass(change.value);
                    const valueText = change.value >= 0 ? `+${formatNumber(change.value)}` : formatNumber(change.value);
                    const pctText = formatPercentage(change.pct);
                    const tooltipAttr = change.source_url ? `title="Source: ${change.source_url}"` : '';

                    changesHTML += `
                        <div class="change-item">
                            <span class="change-label">${periodLabel}</span>
                            <span class="change-value ${valueClass}" ${tooltipAttr}>${pctText}</span>
                            <span class="badge badge-${change.badge}" style="font-size: 0.7rem; padding: 0.25rem 0.5rem;">${change.badge}</span>
                        </div>
                    `;
                }
            }
            changesHTML += '</div>';
        }

        // Build citation links
        let citationHTML = '';
        if (sourceUrls.length > 0) {
            const links = sourceUrls.map((url, i) => `<a href="${url}" target="_blank" rel="noopener">[${i + 1}]</a>`).join(' ');
            citationHTML = `<span class="citation-links">${links}</span>`;
        }

        return `
            <div class="company-item">
                <div class="company-name">${companyName}</div>
                <div class="company-value">${current} employees</div>
                <div class="company-meta">
                    ${dataDate ? `<span>${dataDate}</span>` : ''}
                    ${citationHTML}
                </div>
                ${changesHTML}
            </div>
        `;
    }

    function renderJobPostingCompany(companyName, data) {
        const current = formatNumber(data.current);
        const collectionDate = data.collection_date ? `as of ${data.collection_date}` : '';
        const sourceUrl = data.source_url || '';

        let changesHTML = '';
        if (data.changes && Object.keys(data.changes).length > 0) {
            changesHTML = '<div class="company-changes">';
            for (const [period, change] of Object.entries(data.changes)) {
                const periodLabel = period.replace(/_/g, ' ').replace('ago', '');

                // Check if data is available
                if (change.value === null) {
                    changesHTML += `
                        <div class="change-item">
                            <span class="change-label">${periodLabel}</span>
                            <span class="change-value" style="color: #6b7280;">N/A</span>
                            <span class="badge badge-neutral" style="font-size: 0.7rem; padding: 0.25rem 0.5rem; opacity: 0.5;">no data</span>
                        </div>
                    `;
                } else {
                    const valueClass = getChangeClass(change.value);
                    const valueText = change.value >= 0 ? `+${change.value}` : change.value;

                    changesHTML += `
                        <div class="change-item">
                            <span class="change-label">${periodLabel}</span>
                            <span class="change-value ${valueClass}">${valueText} jobs</span>
                            <span class="badge badge-${change.badge}" style="font-size: 0.7rem; padding: 0.25rem 0.5rem;">${change.badge}</span>
                        </div>
                    `;
                }
            }
            changesHTML += '</div>';
        }

        // Build citation link
        let citationHTML = '';
        if (sourceUrl) {
            citationHTML = `<span class="citation-links"><a href="${sourceUrl}" target="_blank" rel="noopener">[source]</a></span>`;
        }

        return `
            <div class="company-item">
                <div class="company-name">${companyName}</div>
                <div class="company-value">${current} technical jobs</div>
                <div class="company-meta">
                    ${collectionDate ? `<span>${collectionDate}</span>` : ''}
                    ${citationHTML}
                </div>
                ${changesHTML}
            </div>
        `;
    }

    function renderStockIndex(stockIndexData) {
        const indexValue = stockIndexData.current_value.toFixed(2);
        const changes = stockIndexData.changes;

        document.querySelector('.index-value .value').textContent = indexValue;

        const changesHTML = `
            <div class="index-change">
                <span class="period">30 Days</span>
                <span class="value ${getChangeClass(changes['30_day'])}">${formatPercentage(changes['30_day'])}</span>
            </div>
            <div class="index-change">
                <span class="period">1 Year</span>
                <span class="value ${getChangeClass(changes['1_year'])}">${formatPercentage(changes['1_year'])}</span>
            </div>
        `;

        document.getElementById('stockIndexChanges').innerHTML = changesHTML;

        if (stockIndexData.companies) {
            const companiesHTML = Object.entries(stockIndexData.companies)
                .map(([name, data]) => {
                    const change30d = data.change_30_day;
                    const change1y = data.change_1_year;

                    return `
                    <div class="company-item">
                        <div class="company-name">${name}</div>
                        <div class="company-value">${data.current_price.toLocaleString('en-US', { style: 'currency', currency: data.ticker.endsWith('.NS') ? 'INR' : 'USD' })}</div>
                        <div class="company-meta">
                            <span>${data.ticker}</span>
                        </div>
                        <div class="company-changes">
                            <div class="change-item">
                                <span class="change-label">30 Days</span>
                                <span class="change-value ${change30d != null ? getChangeClass(change30d) : ''}">${change30d != null ? formatPercentage(change30d) : 'N/A'}</span>
                            </div>
                            <div class="change-item">
                                <span class="change-label">1 Year</span>
                                <span class="change-value ${change1y != null ? getChangeClass(change1y) : ''}">${change1y != null ? formatPercentage(change1y) : 'N/A'}</span>
                            </div>
                        </div>
                    </div>
                `}).join('');
            document.getElementById('stockCompaniesList').innerHTML = companiesHTML;
        }
    }

    function calculateOverallVerdict(badges) {
        // Count badges by severity
        const collapsingCount = badges.filter(b => b === 'collapsing').length;
        const weakCount = badges.filter(b => b === 'weak').length;

        if (collapsingCount >= 2) {
            return { verdict: 'Yes', cssClass: 'verdict-yes' };
        } else if (weakCount >= 2) {
            return { verdict: 'Maybe', cssClass: 'verdict-maybe' };
        } else {
            return { verdict: 'Not Today', cssClass: 'verdict-not-today' };
        }
    }

    function renderMetrics(data) {
        // Update last updated timestamp
        document.getElementById('lastUpdated').textContent = `Last updated: ${formatDate(data.metadata.last_updated)}`;

        // Calculate overall verdict from 4 main metrics
        const allBadges = [
            data.low_end.headcount.aggregate_badge,
            data.medium_end.headcount.aggregate_badge,
            data.high_end.job_postings.aggregate_badge,
            (data.stock_index || data.low_end.stock_index).aggregate_badge
        ];

        const { verdict, cssClass } = calculateOverallVerdict(allBadges);
        const verdictCard = document.getElementById('overallVerdict');
        verdictCard.className = `verdict-card ${cssClass}`;
        matrixReveal(verdictCard.querySelector('.verdict-value'), verdict);

        // Update AI summary
        document.getElementById('aiSummary').textContent = data.ai_summary;

        // Low-End: IT Consultancies
        let lowEndSummary = null;
        if (data.low_end.headcount.net_headcount_pct_yoy != null) {
            const pct = data.low_end.headcount.net_headcount_pct_yoy;
            const sign = pct > 0 ? '+' : '';
            lowEndSummary = `(${sign}${pct.toFixed(1)}% net headcount YoY)`;
        }
        renderAggregateBadge('lowEndHeadcountBadge', data.low_end.headcount.aggregate_badge, lowEndSummary);

        const lowEndHTML = Object.entries(data.low_end.headcount.companies)
            .map(([name, companyData]) => renderHeadcountCompany(name, companyData))
            .join('');
        document.getElementById('lowEndHeadcount').innerHTML = lowEndHTML;

        // Medium-End: Big Tech
        let mediumEndSummary = null;
        if (data.medium_end.headcount.net_headcount_pct_yoy != null) {
            const pct = data.medium_end.headcount.net_headcount_pct_yoy;
            const sign = pct > 0 ? '+' : '';
            mediumEndSummary = `(${sign}${pct.toFixed(1)}% net headcount YoY)`;
        }
        renderAggregateBadge('mediumEndHeadcountBadge', data.medium_end.headcount.aggregate_badge, mediumEndSummary);

        const mediumEndHTML = Object.entries(data.medium_end.headcount.companies)
            .map(([name, companyData]) => renderHeadcountCompany(name, companyData))
            .join('');
        document.getElementById('mediumEndHeadcount').innerHTML = mediumEndHTML;

        // High-End: AI Labs
        let highEndSummary = null;
        if (data.high_end.job_postings.net_change_pct_yoy != null) {
            const pct = data.high_end.job_postings.net_change_pct_yoy;
            const sign = pct > 0 ? '+' : '';
            highEndSummary = `(${sign}${pct.toFixed(1)}% net jobs YoY)`;
        }
        renderAggregateBadge('highEndJobsBadge', data.high_end.job_postings.aggregate_badge, highEndSummary);

        const highEndHTML = Object.entries(data.high_end.job_postings.companies)
            .map(([name, companyData]) => renderJobPostingCompany(name, companyData))
            .join('');
        document.getElementById('highEndJobs').innerHTML = highEndHTML;

        // Stock Index: IT Consultancies
        const stockIndexData = data.stock_index || data.low_end.stock_index;
        renderAggregateBadge('stockIndexBadge', stockIndexData.aggregate_badge);
        renderStockIndex(stockIndexData);
    }

    function showError(message) {
        const summaryCard = document.querySelector('.summary-card');
        summaryCard.innerHTML = `<div class="error">${message}</div>`;
    }

    // Load metrics on page load
    async function loadMetrics() {
        try {
            const response = await fetch(METRICS_URL);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            renderMetrics(data);
        } catch (error) {
            console.error('Failed to load metrics:', error);
            showError(`Failed to load market data: ${error.message}. Please try again later.`);
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadMetrics);
    } else {
        loadMetrics();
    }
})();

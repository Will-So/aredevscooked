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
                html += `<span class="aggregate-summary">${summaryText}</span>`;
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
                            <span class="badge badge-neutral" style="font-size: 0.8rem; padding: 0.25rem 0.5rem; opacity: 0.5;">no data</span>
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
                            <span class="badge badge-${change.badge}" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;">${change.badge}</span>
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
                const periodLabel = change.label || period.replace(/_/g, ' ').replace('ago', '');

                // Check if data is available
                if (change.value === null) {
                    changesHTML += `
                        <div class="change-item">
                            <span class="change-label" ${change.tooltip ? `tabindex="0" title="${change.tooltip}" aria-label="${periodLabel}. ${change.tooltip}"` : ''}>${periodLabel}${change.tooltip ? ' ⓘ' : ''}</span>
                            <span class="change-value" style="color: #6b7280;">N/A</span>
                            <span class="badge badge-neutral" style="font-size: 0.8rem; padding: 0.25rem 0.5rem; opacity: 0.5;">no data</span>
                        </div>
                    `;
                } else {
                    const valueClass = getChangeClass(change.value);
                    const valueText = change.value >= 0 ? `+${change.value}` : change.value;

                    changesHTML += `
                        <div class="change-item">
                            <span class="change-label" ${change.tooltip ? `tabindex="0" title="${change.tooltip}" aria-label="${periodLabel}. ${change.tooltip}"` : ''}>${periodLabel}${change.tooltip ? ' ⓘ' : ''}</span>
                            <span class="change-value ${valueClass}">${valueText} jobs</span>
                            <span class="badge badge-${change.badge}" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;">${change.badge}</span>
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

    function renderIndeedIndex(indeedData) {
        if (!indeedData) return;

        let indeedSummary = null;
        if (indeedData.changes && indeedData.changes['1_year'] && indeedData.changes['1_year'].pct != null) {
            indeedSummary = `(${formatPercentage(indeedData.changes['1_year'].pct)} index YoY)`;
        }
        renderAggregateBadge('indeedIndexBadge', indeedData.aggregate_badge, indeedSummary);

        const changes = indeedData.changes || {};
        const periodLabels = { '30_day': '30 Days', '1_year': '1 Year', 'q1_2023': 'vs Q1 2023' };
        const orderedPeriods = ['30_day', '1_year', 'q1_2023'];
        let changesHTML = '<div class="index-changes">';

        for (const period of orderedPeriods) {
            const change = changes[period];
            if (!change) {
                continue;
            }
            const periodLabel = periodLabels[period] || period;
            if (change.pct == null) {
                changesHTML += `
                    <div class="index-change">
                        <span class="period">${periodLabel}</span>
                        <span class="value neutral">N/A</span>
                    </div>
                `;
            } else {
                changesHTML += `
                    <div class="index-change">
                        <span class="period">${periodLabel}</span>
                        <span class="value ${getChangeClass(change.pct)}">${formatPercentage(change.pct)}</span>
                    </div>
                `;
            }
        }
        changesHTML += '</div>';

        let citationHTML = '';
        if (indeedData.source_url) {
            citationHTML = `<span class="citation-links"><a href="${indeedData.source_url}" target="_blank" rel="noopener">[FRED source]</a></span>`;
        }

        let relativeHTML = '';
        if (indeedData.relative_to_market) {
            const relChanges = indeedData.relative_to_market.changes || {};
            const relBadge = indeedData.relative_to_market.aggregate_badge || 'neutral';
            let relChangesHTML = '<div class="index-changes">';
            for (const period of orderedPeriods) {
                const change = relChanges[period];
                if (!change) continue;
                const periodLabel = periodLabels[period] || period;
                if (change.pct == null) {
                    relChangesHTML += `
                        <div class="index-change">
                            <span class="period">${periodLabel}</span>
                            <span class="value neutral">N/A</span>
                        </div>
                    `;
                } else {
                    relChangesHTML += `
                        <div class="index-change">
                            <span class="period">${periodLabel}</span>
                            <span class="value ${getChangeClass(change.pct)}">${formatPercentage(change.pct)}</span>
                        </div>
                    `;
                }
            }
            relChangesHTML += '</div>';

            const totalMarketUrl = indeedData.total_market && indeedData.total_market.source_url;
            const totalMarketCitation = totalMarketUrl
                ? `<div class="company-meta index-meta"><span class="citation-links"><a href="${totalMarketUrl}" target="_blank" rel="noopener">[FRED total market source]</a></span></div>`
                : '';

            const badgeClass = relBadge.replace('_', '-');
            relativeHTML = `
                <div class="stock-index indeed-index relative-market">
                    <div class="index-value">
                        <span class="label">Relative to Total Job Market</span>
                        <span class="badge ${badgeClass}">${relBadge.replace('_', ' ')}</span>
                    </div>
                    ${totalMarketCitation}
                    ${relChangesHTML}
                </div>
            `;
        }

        const html = `
            <div class="stock-index indeed-index">
                <div class="index-value">
                    <span class="value">${indeedData.current_value.toFixed(2)}</span>
                    <span class="label">Index Value</span>
                </div>
                <div class="company-meta index-meta">
                    ${indeedData.date ? `<span>as of ${indeedData.date}</span>` : ''}
                    ${citationHTML}
                </div>
                ${changesHTML}
            </div>
            ${relativeHTML}
        `;

        document.getElementById('indeedIndexData').innerHTML = html;
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

        if (stockIndexData.relative_to_spy) {
            const relChanges = stockIndexData.relative_to_spy.changes || {};
            const relBadge = stockIndexData.relative_to_spy.aggregate_badge || 'neutral';
            let relChangesHTML = '<div class="index-changes">';

            const periods = [
                { key: '30_day', label: '30 Days' },
                { key: '1_year', label: '1 Year' }
            ];

            for (const { key, label } of periods) {
                const change = relChanges[key];
                if (!change) continue;
                if (change.pct == null) {
                    relChangesHTML += `
                        <div class="index-change">
                            <span class="period">${label}</span>
                            <span class="value neutral">N/A</span>
                        </div>
                    `;
                } else {
                    relChangesHTML += `
                        <div class="index-change">
                            <span class="period">${label}</span>
                            <span class="value ${getChangeClass(change.pct)}">${formatPercentage(change.pct)}</span>
                        </div>
                    `;
                }
            }
            relChangesHTML += '</div>';

            const badgeClass = relBadge.replace('_', '-');
            const relativeHTML = `
                <div class="stock-index relative-market">
                    <div class="index-value">
                        <span class="label">Relative to S&P 500</span>
                        <span class="badge ${badgeClass}">${relBadge.replace('_', ' ')}</span>
                    </div>
                    ${relChangesHTML}
                </div>
            `;

            document.getElementById('stockCompaniesList')
                .insertAdjacentHTML('beforebegin', relativeHTML);
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
        document.getElementById('lastUpdated').innerHTML = `Last updated: ${formatDate(data.metadata.last_updated)} <a href="https://substack.com/home/post/p-191200751" target="_blank" rel="noopener noreferrer" class="read-more-link">Read More</a>`;

        // Calculate overall verdict from 4 main metrics
        const allBadges = [
            (data.stock_index || data.low_end.stock_index).aggregate_badge,
            data.indeed_index ? data.indeed_index.aggregate_badge : 'neutral',
            data.medium_end.headcount.aggregate_badge,
            data.high_end.job_postings.aggregate_badge,
        ];

        const { verdict, cssClass } = calculateOverallVerdict(allBadges);
        const verdictCard = document.getElementById('overallVerdict');
        verdictCard.className = `verdict-card ${cssClass}`;
        matrixReveal(verdictCard.querySelector('.verdict-value'), verdict);

        // Update AI summary
        document.getElementById('aiSummary').textContent = data.ai_summary;

        // Indeed Job Postings Index
        if (data.indeed_index) {
            renderIndeedIndex(data.indeed_index);
        }

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

    function setupMobileCollapse() {
        const collapsibleIds = ['stockCompaniesList', 'lowEndHeadcount', 'mediumEndHeadcount', 'highEndJobs'];

        collapsibleIds.forEach(function(id) {
            const list = document.getElementById(id);
            if (!list || !list.children.length) return;

            const btn = document.createElement('button');
            btn.className = 'details-toggle';
            btn.setAttribute('aria-expanded', 'false');
            btn.innerHTML = '&#9654; Show companies';

            btn.addEventListener('click', function() {
                const expanded = list.classList.toggle('expanded');
                btn.setAttribute('aria-expanded', expanded);
                btn.innerHTML = expanded ? '&#9660; Hide companies' : '&#9654; Show companies';
            });

            list.parentNode.insertBefore(btn, list);
        });
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
            setupMobileCollapse();
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

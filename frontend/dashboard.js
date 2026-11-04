'use strict';

// ── Auth Guard & Fetch Interceptor ──────────────────────────────────────────
const _authToken = sessionStorage.getItem('ledger_access_token');
if (!_authToken) {
    window.location.href = 'index.html';
}

const _originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
    options = options || {};
    options.headers = options.headers || {};
    const curToken = sessionStorage.getItem('ledger_access_token');
    if (curToken) {
        if (options.headers instanceof Headers) {
            if (!options.headers.has('Authorization')) {
                options.headers.set('Authorization', 'Bearer ' + curToken);
            }
        } else if (Array.isArray(options.headers)) {
            options.headers.push(['Authorization', 'Bearer ' + curToken]);
        } else {
            if (!options.headers['Authorization']) {
                options.headers['Authorization'] = 'Bearer ' + curToken;
            }
        }
    }
    const response = await _originalFetch(url, options);
    if (response.status === 401) {
        sessionStorage.removeItem('ledger_access_token');
        window.location.href = 'index.html';
    }
    return response;
};

const API_BASE = window.location.origin.includes(':8000') 
    ? window.location.origin 
    : 'http://127.0.0.1:8000';

const STATE = {
    accounts: [],
    parties: [],
    vouchers: [],
    expenses: [],
    expenseDateFilter: null,
    summary: null,
    profile: null,
    offlineQueue: []
};

// Formatting helpers
function formatPKR(val) {
    const num = parseFloat(val) || 0;
    return 'PKR ' + num.toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(isoStr) {
    if (!isoStr) return '-';
    const d = new Date(isoStr);
    return isNaN(d.getTime()) ? isoStr : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// DOM Elements
const DOM = {
    // Views
    navLinks: document.querySelectorAll('.nav-link'),
    views: document.querySelectorAll('.view-section'),

    // Topbar
    headerCompanyName: document.getElementById('headerCompanyName'),
    headerCompanyAddress: document.getElementById('headerCompanyAddress'),
    systemStatusText: document.getElementById('systemStatusText'),
    systemStatusPill: document.getElementById('systemStatusPill'),
    topUserName: document.getElementById('topUserName'),
    topUserRole: document.getElementById('topUserRole'),
    userAvatarText: document.getElementById('userAvatarText'),
    btnLogout: document.getElementById('btnLogout'),
    btnQuickVoucher: document.getElementById('btnQuickVoucher'),
    btnTopAnnualReport: document.getElementById('btnTopAnnualReport'),
    btnTopMonthlyReport: document.getElementById('btnTopMonthlyReport'),
    btnHeaderProfile: document.getElementById('btnHeaderProfile'),
    brandHomeBtn: document.getElementById('brandHomeBtn'),

    // Dashboard View
    btnRefreshDashboard: document.getElementById('btnRefreshDashboard'),
    btnQuickAnnualReport: document.getElementById('btnQuickAnnualReport'),
    btnQuickMonthlyReport: document.getElementById('btnQuickMonthlyReport'),
    btnOpenNewVoucherModal: document.getElementById('btnOpenNewVoucherModal'),
    kpiTotalIncome: document.getElementById('kpiTotalIncome'),
    kpiRemainingAmt: document.getElementById('kpiRemainingAmt'),
    cardRemainingAmt: document.getElementById('cardRemainingAmt'),
    kpiAmountReceived: document.getElementById('kpiAmountReceived'),
    kpiNetReceivedMinusExpense: document.getElementById('kpiNetReceivedMinusExpense'),
    cardNetReceivedMinusExpense: document.getElementById('cardNetReceivedMinusExpense'),
    statNetReceivedMinusExpense: document.getElementById('statNetReceivedMinusExpense'),
    stripNetReceivedMinusExpense: document.getElementById('stripNetReceivedMinusExpense'),
    kpiLiquidFunds: document.getElementById('kpiLiquidFunds'),
    kpiReceivables: document.getElementById('kpiReceivables'),
    kpiPayables: document.getElementById('kpiPayables'),
    kpiWorkingCapital: document.getElementById('kpiWorkingCapital'),
    cashFlowChartWrap: document.getElementById('cashFlowChartWrap'),
    statGrossRevenue: document.getElementById('statGrossRevenue'),
    statTotalExpense: document.getElementById('statTotalExpense'),
    statNetProfit: document.getElementById('statNetProfit'),
    statNetMargin: document.getElementById('statNetMargin'),
    recentVouchersTableBody: document.getElementById('recentVouchersTableBody'),
    btnViewAllVouchers: document.getElementById('btnViewAllVouchers'),

    // Vouchers View
    btnCreateVoucherTop: document.getElementById('btnCreateVoucherTop'),
    voucherFilterTabs: document.getElementById('voucherFilterTabs'),
    voucherSearchInput: document.getElementById('voucherSearchInput'),
    vouchersListBody: document.getElementById('vouchersListBody'),

    // Accounts View
    btnAddNewAccount: document.getElementById('btnAddNewAccount'),
    accountTypeTabs: document.getElementById('accountTypeTabs'),
    accountSearchInput: document.getElementById('accountSearchInput'),
    accountsTableBody: document.getElementById('accountsTableBody'),

    // Parties View
    btnAddNewParty: document.getElementById('btnAddNewParty'),
    partyFilterTabs: document.getElementById('partyFilterTabs'),
    partySearchInput: document.getElementById('partySearchInput'),
    partiesTableBody: document.getElementById('partiesTableBody'),
    partyTotalReceivable: document.getElementById('partyTotalReceivable'),
    partyTotalPayable: document.getElementById('partyTotalPayable'),

    // Reports View
    reportSubTabs: document.getElementById('reportSubTabs'),
    subViewTrialBalance: document.getElementById('subViewTrialBalance'),
    subViewProfitLoss: document.getElementById('subViewProfitLoss'),
    subViewGeneralLedger: document.getElementById('subViewGeneralLedger'),
    subViewPartyLedger: document.getElementById('subViewPartyLedger'),
    trialBalanceTableBody: document.getElementById('trialBalanceTableBody'),
    trialBalanceTableFoot: document.getElementById('trialBalanceTableFoot'),
    trialBalanceStatusBadge: document.getElementById('trialBalanceStatusBadge'),
    plRevenuesTable: document.getElementById('plRevenuesTable'),
    plExpensesTable: document.getElementById('plExpensesTable'),
    plNetProfitSummary: document.getElementById('plNetProfitSummary'),
    glAccountSelect: document.getElementById('glAccountSelect'),
    btnLoadGlStatement: document.getElementById('btnLoadGlStatement'),
    glStatementTableBody: document.getElementById('glStatementTableBody'),
    partyStatementSelect: document.getElementById('partyStatementSelect'),
    btnLoadPartyStatement: document.getElementById('btnLoadPartyStatement'),
    partyStatementInfoCard: document.getElementById('partyStatementInfoCard'),
    psiName: document.getElementById('psiName'),
    psiContact: document.getElementById('psiContact'),
    psiPhone: document.getElementById('psiPhone'),
    psiBalance: document.getElementById('psiBalance'),
    btnTopPartyStatement: document.getElementById('btnTopPartyStatement'),
    glStatementFromDate: document.getElementById('glStatementFromDate'),
    glStatementToDate: document.getElementById('glStatementToDate'),
    glStatementTableFoot: document.getElementById('glStatementTableFoot'),
    partyStatementFromDate: document.getElementById('partyStatementFromDate'),
    partyStatementToDate: document.getElementById('partyStatementToDate'),
    partyStatementTableFoot: document.getElementById('partyStatementTableFoot'),
    partyStatementTableBody: document.getElementById('partyStatementTableBody'),

    // Annual Report
    subViewAnnualReport: document.getElementById('subViewAnnualReport'),
    annualYearSelect: document.getElementById('annualYearSelect'),
    btnLoadAnnualReport: document.getElementById('btnLoadAnnualReport'),
    btnAnnualWholeYear: document.getElementById('btnAnnualWholeYear'),
    annualKpiStrip: document.getElementById('annualKpiStrip'),
    annualTotalInflow: document.getElementById('annualTotalInflow'),
    annualTotalOutflow: document.getElementById('annualTotalOutflow'),
    annualNetCash: document.getElementById('annualNetCash'),
    annualVoucherCount: document.getElementById('annualVoucherCount'),
    annualProfitBanner: document.getElementById('annualProfitBanner'),
    annualNetProfit: document.getElementById('annualNetProfit'),
    annualRevenue: document.getElementById('annualRevenue'),
    annualExpense: document.getElementById('annualExpense'),
    annualReportTableBody: document.getElementById('annualReportTableBody'),
    annualReportTableFoot: document.getElementById('annualReportTableFoot'),
    annualTypeSummary: document.getElementById('annualTypeSummary'),
    annualTypeSummaryBody: document.getElementById('annualTypeSummaryBody'),

    // Monthly Report
    subViewMonthlyReport: document.getElementById('subViewMonthlyReport'),
    monthlyYearSelect: document.getElementById('monthlyYearSelect'),
    monthlyMonthSelect: document.getElementById('monthlyMonthSelect'),
    btnLoadMonthlyReport: document.getElementById('btnLoadMonthlyReport'),
    btnMonthly1to30: document.getElementById('btnMonthly1to30'),
    monthlyPeriodBanner: document.getElementById('monthlyPeriodBanner'),
    monthlyPeriodTitle: document.getElementById('monthlyPeriodTitle'),
    monthlyKpiStrip: document.getElementById('monthlyKpiStrip'),
    monthlyTotalInflow: document.getElementById('monthlyTotalInflow'),
    monthlyTotalOutflow: document.getElementById('monthlyTotalOutflow'),
    monthlyNetCash: document.getElementById('monthlyNetCash'),
    monthlyVoucherCount: document.getElementById('monthlyVoucherCount'),
    monthlyTypeBreakdown: document.getElementById('monthlyTypeBreakdown'),
    monthlyReportTableBody: document.getElementById('monthlyReportTableBody'),
    monthlyReportTableFoot: document.getElementById('monthlyReportTableFoot'),
    monthlyDailySummaryWrap: document.getElementById('monthlyDailySummaryWrap'),
    monthlyDailySummaryBody: document.getElementById('monthlyDailySummaryBody'),

    // Settings View
    settingsProfileForm: document.getElementById('settingsProfileForm'),
    settingsAlertBanner: document.getElementById('settingsAlertBanner'),
    setFullName: document.getElementById('setFullName'),
    setEmail: document.getElementById('setEmail'),
    setCompanyName: document.getElementById('setCompanyName'),
    setPhone: document.getElementById('setPhone'),
    setAddress: document.getElementById('setAddress'),
    setNewPassword: document.getElementById('setNewPassword'),
    setConfirmPassword: document.getElementById('setConfirmPassword'),

    // Sync View
    btnExportBackup: document.getElementById('btnExportBackup'),
    btnForceSyncVouchers: document.getElementById('btnForceSyncVouchers'),
    btnPingHealth: document.getElementById('btnPingHealth'),
    engineInfoText: document.getElementById('engineInfoText'),

    // Modals
    modalVoucher: document.getElementById('modalVoucher'),
    voucherCreateForm: document.getElementById('voucherCreateForm'),
    vFormVoucherNumber: document.getElementById('vFormVoucherNumber'),
    vFormType: document.getElementById('vFormType'),
    vFormDate: document.getElementById('vFormDate'),
    vFormRef: document.getElementById('vFormRef'),
    vFormNarration: document.getElementById('vFormNarration'),
    btnAddVoucherRow: document.getElementById('btnAddVoucherRow'),
    voucherLinesBody: document.getElementById('voucherLinesBody'),
    vTotalDebit: document.getElementById('vTotalDebit'),
    vTotalCredit: document.getElementById('vTotalCredit'),
    vBalanceBadge: document.getElementById('vBalanceBadge'),
    btnSubmitVoucher: document.getElementById('btnSubmitVoucher'),

    modalVoucherSlip: document.getElementById('modalVoucherSlip'),
    slipCompanyName: document.getElementById('slipCompanyName'),
    slipCompanyAddress: document.getElementById('slipCompanyAddress'),
    slipVoucherTypeTitle: document.getElementById('slipVoucherTypeTitle'),
    slipVoucherNumber: document.getElementById('slipVoucherNumber'),
    slipReference: document.getElementById('slipReference'),
    slipDate: document.getElementById('slipDate'),
    slipNarration: document.getElementById('slipNarration'),
    slipEntriesTableBody: document.getElementById('slipEntriesTableBody'),
    slipEntriesTableFoot: document.getElementById('slipEntriesTableFoot'),
    slipPreparedBy: document.getElementById('slipPreparedBy'),
    btnDeleteSlipVoucher: document.getElementById('btnDeleteSlipVoucher'),
    btnPrintSlipBtn: document.getElementById('btnPrintSlipBtn'),

    modalParty: document.getElementById('modalParty'),
    partyModalTitle: document.getElementById('partyModalTitle'),
    partyForm: document.getElementById('partyForm'),
    partyFormId: document.getElementById('partyFormId'),
    partyFormName: document.getElementById('partyFormName'),
    partyFormType: document.getElementById('partyFormType'),
    partyFormContact: document.getElementById('partyFormContact'),
    partyFormPhone: document.getElementById('partyFormPhone'),
    partyFormEmail: document.getElementById('partyFormEmail'),
    partyFormCity: document.getElementById('partyFormCity'),
    partyFormAddress: document.getElementById('partyFormAddress'),
    partyFormCreditLimit: document.getElementById('partyFormCreditLimit'),
    partyFormBalance: document.getElementById('partyFormBalance'),
    partyOpeningBalGroup: document.getElementById('partyOpeningBalGroup'),

    modalAccount: document.getElementById('modalAccount'),
    accountModalTitle: document.getElementById('accountModalTitle'),
    accountForm: document.getElementById('accountForm'),
    accountFormId: document.getElementById('accountFormId'),
    accountFormCode: document.getElementById('accountFormCode'),
    accountFormName: document.getElementById('accountFormName'),
    accountFormType: document.getElementById('accountFormType'),
    accountFormBalance: document.getElementById('accountFormBalance'),
    accountFormDesc: document.getElementById('accountFormDesc'),
    accountOpeningBalGroup: document.getElementById('accountOpeningBalGroup'),

    // Daily & Date-wise Expenses
    btnQuickExpense: document.getElementById('btnQuickExpense'),
    navLinkDailyExpenses: document.getElementById('navLinkDailyExpenses'),
    btnOpenExpenseModal: document.getElementById('btnOpenExpenseModal'),
    btnOpenExpenseModalFromSection: document.getElementById('btnOpenExpenseModalFromSection'),
    kpiTotalExpenses: document.getElementById('kpiTotalExpenses'),
    kpiTodayExpenseSubtitle: document.getElementById('kpiTodayExpenseSubtitle'),
    dailyExpensesSection: document.getElementById('dailyExpensesSection'),
    expenseFilterDate: document.getElementById('expenseFilterDate'),
    btnExpenseFilterToday: document.getElementById('btnExpenseFilterToday'),
    btnExpenseFilterAll: document.getElementById('btnExpenseFilterAll'),
    stripTodayExpense: document.getElementById('stripTodayExpense'),
    stripFilteredExpense: document.getElementById('stripFilteredExpense'),
    stripAllTimeExpense: document.getElementById('stripAllTimeExpense'),
    expenseTableBody: document.getElementById('expenseTableBody'),

    // Expense Modal
    modalExpense: document.getElementById('modalExpense'),
    formAddExpense: document.getElementById('formAddExpense'),
    expFormDate: document.getElementById('expFormDate'),
    expFormAmount: document.getElementById('expFormAmount'),

    expFormNarration: document.getElementById('expFormNarration'),
    expFormReference: document.getElementById('expFormReference'),
    btnSubmitExpense: document.getElementById('btnSubmitExpense')
};

// Initial Startup
document.addEventListener('DOMContentLoaded', async () => {
    initNavigation();
    initModalClosers();
    initDatePickers();
    await loadUserProfile();
    await refreshAllData();
});

function initDatePickers() {
    const today = new Date().toISOString().split('T')[0];
    if (DOM.vFormDate) {
        DOM.vFormDate.value = today;
    }
    if (DOM.expenseFilterDate && !DOM.expenseFilterDate.value) {
        DOM.expenseFilterDate.value = today;
    }
    if (DOM.expFormDate && !DOM.expFormDate.value) {
        DOM.expFormDate.value = today;
    }
}

// Navigation Tab Switching
function initNavigation() {
    DOM.navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetViewId = link.getAttribute('data-view');
            switchView(targetViewId);
        });
    });

    if (DOM.brandHomeBtn) {
        DOM.brandHomeBtn.addEventListener('click', () => switchView('dashboardView'));
    }

    if (DOM.btnViewAllVouchers) {
        DOM.btnViewAllVouchers.addEventListener('click', () => switchView('vouchersView'));
    }

    // Quick Jump to Reports Helpers
    function openReportTab(reportKey) {
        switchView('reportsView');
        if (DOM.reportSubTabs) {
            DOM.reportSubTabs.querySelectorAll('.filter-tab').forEach(b => {
                b.classList.toggle('active', b.getAttribute('data-report') === reportKey);
            });
        }
        switchReportSubView(reportKey);
    }

    if (DOM.btnTopPartyStatement) {
        DOM.btnTopPartyStatement.addEventListener('click', () => openReportTab('partyLedger'));
    }
    if (DOM.btnTopAnnualReport) {
        DOM.btnTopAnnualReport.addEventListener('click', () => openReportTab('annualReport'));
    }
    if (DOM.btnQuickAnnualReport) {
        DOM.btnQuickAnnualReport.addEventListener('click', () => openReportTab('annualReport'));
    }
    if (DOM.btnTopMonthlyReport) {
        DOM.btnTopMonthlyReport.addEventListener('click', () => openReportTab('monthlyReport'));
    }
    if (DOM.btnQuickMonthlyReport) {
        DOM.btnQuickMonthlyReport.addEventListener('click', () => openReportTab('monthlyReport'));
    }

    if (DOM.btnHeaderProfile) {
        DOM.btnHeaderProfile.addEventListener('click', () => switchView('settingsView'));
    }

    if (DOM.btnLogout) {
        DOM.btnLogout.addEventListener('click', () => {
            sessionStorage.removeItem('ledger_access_token');
            window.location.href = 'index.html';
        });
    }

    // Refresh Dashboard
    if (DOM.btnRefreshDashboard) {
        DOM.btnRefreshDashboard.addEventListener('click', refreshAllData);
    }

    // Open Voucher Modal Buttons
    if (DOM.btnQuickVoucher) {
        DOM.btnQuickVoucher.addEventListener('click', openVoucherModal);
    }
    if (DOM.btnOpenNewVoucherModal) {
        DOM.btnOpenNewVoucherModal.addEventListener('click', openVoucherModal);
    }
    if (DOM.btnCreateVoucherTop) {
        DOM.btnCreateVoucherTop.addEventListener('click', openVoucherModal);
    }

    // New Party Modal
    if (DOM.btnAddNewParty) {
        DOM.btnAddNewParty.addEventListener('click', () => openPartyModal(null));
    }

    // New Account Modal
    if (DOM.btnAddNewAccount) {
        DOM.btnAddNewAccount.addEventListener('click', () => openAccountModal(null));
    }

    // Add Expense Buttons & Navigation
    if (DOM.btnQuickExpense) {
        DOM.btnQuickExpense.addEventListener('click', openExpenseModal);
    }
    if (DOM.btnOpenExpenseModal) {
        DOM.btnOpenExpenseModal.addEventListener('click', openExpenseModal);
    }
    if (DOM.btnOpenExpenseModalFromSection) {
        DOM.btnOpenExpenseModalFromSection.addEventListener('click', openExpenseModal);
    }
    if (DOM.navLinkDailyExpenses) {
        DOM.navLinkDailyExpenses.addEventListener('click', () => {
            switchView('dashboardView');
            setTimeout(() => {
                if (DOM.dailyExpensesSection) {
                    DOM.dailyExpensesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 100);
        });
    }

    // Expense Filters
    if (DOM.btnExpenseFilterToday) {
        DOM.btnExpenseFilterToday.addEventListener('click', () => {
            const todayStr = new Date().toISOString().split('T')[0];
            if (DOM.expenseFilterDate) DOM.expenseFilterDate.value = todayStr;
            fetchExpenses(todayStr);
        });
    }
    if (DOM.btnExpenseFilterAll) {
        DOM.btnExpenseFilterAll.addEventListener('click', () => {
            if (DOM.expenseFilterDate) DOM.expenseFilterDate.value = '';
            fetchExpenses(null);
        });
    }
    if (DOM.expenseFilterDate) {
        DOM.expenseFilterDate.addEventListener('change', () => {
            fetchExpenses(DOM.expenseFilterDate.value);
        });
    }

    // Reports sub-tabs
    if (DOM.reportSubTabs) {
        DOM.reportSubTabs.querySelectorAll('.filter-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                DOM.reportSubTabs.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const report = btn.getAttribute('data-report');
                switchReportSubView(report);
            });
        });
    }

    // Voucher register filters & search
    if (DOM.voucherFilterTabs) {
        DOM.voucherFilterTabs.querySelectorAll('.filter-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                DOM.voucherFilterTabs.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderVouchersTable();
            });
        });
    }
    if (DOM.voucherSearchInput) {
        DOM.voucherSearchInput.addEventListener('input', renderVouchersTable);
    }

    // Accounts filters & search
    if (DOM.accountTypeTabs) {
        DOM.accountTypeTabs.querySelectorAll('.filter-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                DOM.accountTypeTabs.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderAccountsTable();
            });
        });
    }
    if (DOM.accountSearchInput) {
        DOM.accountSearchInput.addEventListener('input', renderAccountsTable);
    }

    // Parties filters & search
    if (DOM.partyFilterTabs) {
        DOM.partyFilterTabs.querySelectorAll('.filter-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                DOM.partyFilterTabs.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderPartiesTable();
            });
        });
    }
    if (DOM.partySearchInput) {
        DOM.partySearchInput.addEventListener('input', renderPartiesTable);
    }

    // GL and Party Statement triggers
    if (DOM.btnLoadGlStatement) {
        DOM.btnLoadGlStatement.addEventListener('click', loadGeneralLedgerStatement);
    }
    if (DOM.btnLoadPartyStatement) {
        DOM.btnLoadPartyStatement.addEventListener('click', loadPartyStatement);
    }

    // Annual & Monthly Report triggers
    if (DOM.btnLoadAnnualReport) {
        DOM.btnLoadAnnualReport.addEventListener('click', loadAnnualReport);
    }
    if (DOM.btnAnnualWholeYear) {
        DOM.btnAnnualWholeYear.addEventListener('click', loadAnnualReport);
    }
    if (DOM.btnLoadMonthlyReport) {
        DOM.btnLoadMonthlyReport.addEventListener('click', loadMonthlyReport);
    }
    if (DOM.btnMonthly1to30) {
        DOM.btnMonthly1to30.addEventListener('click', loadMonthlyReport);
    }

    // Forms
    if (DOM.voucherCreateForm) {
        DOM.voucherCreateForm.addEventListener('submit', handleVoucherSubmit);
    }
    if (DOM.btnAddVoucherRow) {
        DOM.btnAddVoucherRow.addEventListener('click', () => addVoucherLineRow());
    }
    if (DOM.partyForm) {
        DOM.partyForm.addEventListener('submit', handlePartySubmit);
    }
    if (DOM.accountForm) {
        DOM.accountForm.addEventListener('submit', handleAccountSubmit);
    }
    if (DOM.settingsProfileForm) {
        DOM.settingsProfileForm.addEventListener('submit', handleProfileUpdate);
    }
    const formAddCf = document.getElementById('formAddCustomField');
    if (formAddCf) {
        formAddCf.addEventListener('submit', handleAddCustomField);
    }

    if (DOM.formAddExpense) {
        DOM.formAddExpense.addEventListener('submit', handleExpenseSubmit);
    }

    // Backup & Sync buttons
    if (DOM.btnExportBackup) {
        DOM.btnExportBackup.addEventListener('click', exportDatabaseJson);
    }
    if (DOM.btnForceSyncVouchers) {
        DOM.btnForceSyncVouchers.addEventListener('click', forceSyncOfflineQueue);
    }
    if (DOM.btnPingHealth) {
        DOM.btnPingHealth.addEventListener('click', checkSystemHealth);
    }

    // Print Voucher
        if (DOM.btnDeleteSlipVoucher) {
        DOM.btnDeleteSlipVoucher.addEventListener('click', () => {
            if (STATE.currentSlipVoucherId) {
                deleteVoucher(STATE.currentSlipVoucherId, STATE.currentSlipVoucherNumber);
            }
        });
    }

    if (DOM.btnPrintSlipBtn) {
        DOM.btnPrintSlipBtn.addEventListener('click', () => {
            printVoucherSlipNow();
        });
    }
}

function switchView(viewId) {
    DOM.views.forEach(view => {
        if (view.id === viewId) {
            view.classList.add('active');
        } else {
            view.classList.remove('active');
        }
    });

    DOM.navLinks.forEach(link => {
        if (link.getAttribute('data-view') === viewId) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (viewId === 'incomeView') fetchIncomes();
    if (viewId === 'paymentsView') fetchPayments();
    if (viewId === 'ledgerView') fetchUnifiedLedger();
    if (viewId === 'gatePassView') {
        if (typeof fetchGatePasses === 'function') fetchGatePasses();
    }
    if (viewId === 'expensesView') {
        if (typeof fetchExpenses === 'function') fetchExpenses(DOM.expenseFilterDate && DOM.expenseFilterDate.value ? DOM.expenseFilterDate.value : null);
    }
    if (viewId === 'vouchersView') {
        if (typeof fetchVouchers === 'function') fetchVouchers();
    }
    if (viewId === 'customersView') {
        if (typeof fetchCustomers === 'function') fetchCustomers();
    }
    if (viewId === 'suppliersView') {
        if (typeof fetchSuppliers === 'function') fetchSuppliers();
    }
}

function switchReportSubView(reportKey) {
    DOM.subViewTrialBalance.style.display = reportKey === 'trialBalance' ? 'block' : 'none';
    DOM.subViewProfitLoss.style.display = reportKey === 'profitLoss' ? 'block' : 'none';
    DOM.subViewGeneralLedger.style.display = reportKey === 'generalLedger' ? 'block' : 'none';
    DOM.subViewPartyLedger.style.display = reportKey === 'partyLedger' ? 'block' : 'none';
    if (DOM.subViewAnnualReport) DOM.subViewAnnualReport.style.display = reportKey === 'annualReport' ? 'block' : 'none';
    if (DOM.subViewMonthlyReport) DOM.subViewMonthlyReport.style.display = reportKey === 'monthlyReport' ? 'block' : 'none';

    if (reportKey === 'trialBalance') loadTrialBalanceReport();
    if (reportKey === 'profitLoss') loadProfitLossReport();
    if (reportKey === 'generalLedger') populateGlAccountDropdown();
    if (reportKey === 'partyLedger') populatePartyDropdown();
    if (reportKey === 'annualReport') {
        initAnnualReportControls();
        loadAnnualReport();
    }
    if (reportKey === 'monthlyReport') {
        initMonthlyReportControls();
        loadMonthlyReport();
    }
}

function initModalClosers() {
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.getAttribute('data-close-modal');
            const target = document.getElementById(modalId);
            if (target) target.setAttribute('hidden', '');
        });
    });

    document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.setAttribute('hidden', '');
            }
        });
    });
}

// ---------------------------------------------------------------------------
// DATA FETCHING & SYNCHRONIZATION
// ---------------------------------------------------------------------------
async function refreshAllData() {
    try {
        await Promise.all([
            fetchDashboardSummary(),
            fetchAccounts(),
            fetchParties(),
            fetchVouchers(),
            fetchExpenses(DOM.expenseFilterDate && DOM.expenseFilterDate.value ? DOM.expenseFilterDate.value : null),
            (typeof fetchGatePasses === 'function' ? fetchGatePasses() : Promise.resolve())
        ]);
        checkSystemHealth();
    } catch (err) {
        console.warn('Network issue fetching live data:', err);
        setOfflineIndicator();
    }
}

async function checkSystemHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/health`);
        if (res.ok) {
            const data = await res.json();
            DOM.systemStatusText.innerHTML = `FastAPI Online &bull; ${data.currency}`;
            DOM.systemStatusPill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            if (DOM.engineInfoText) {
                DOM.engineInfoText.innerHTML = `Engine: ${data.engine} &bull; Currency: ${data.currency}`;
            }
        }
    } catch (e) {
        setOfflineIndicator();
    }
}

function setOfflineIndicator() {
    DOM.systemStatusText.innerHTML = `Offline Cache &bull; Local Mode`;
    DOM.systemStatusPill.style.borderColor = 'rgba(245, 158, 11, 0.4)';
}

async function fetchDashboardSummary() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`);
        if (!res.ok) throw new Error('Failed to load dashboard summary');
        const data = await res.json();
        STATE.summary = data;
        renderDashboardKPIs(data);
        renderCashFlowChart(data.monthly_flow || []);
        renderRecentVouchers(data.recent_vouchers || []);
    } catch (err) {
        console.error('fetchDashboardSummary error:', err);
    }
}

async function fetchAccounts() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/accounts`);
        if (!res.ok) throw new Error('Failed to load accounts');
        const data = await res.json();
        STATE.accounts = data;
        renderAccountsTable();
        populateGlAccountDropdown();
    } catch (err) {
        console.error('fetchAccounts error:', err);
    }
}

async function fetchParties() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/parties`);
        if (!res.ok) throw new Error('Failed to load parties');
        const data = await res.json();
        STATE.parties = data;
        renderPartiesTable();
        populatePartyDropdown();
    } catch (err) {
        console.error('fetchParties error:', err);
    }
}

async function fetchVouchers() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/vouchers?limit=100`);
        if (!res.ok) throw new Error('Failed to load vouchers');
        const data = await res.json();
        STATE.vouchers = data;
        renderVouchersTable();
    } catch (err) {
        console.error('fetchVouchers error:', err);
    }
}

async function loadUserProfile() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/auth/profile`);
        if (res.ok) {
            const user = await res.json();
            STATE.profile = user;
            applyUserProfileToUI(user);
        }
    } catch (err) {
        console.warn('Could not fetch user profile:', err);
    }
}

function applyUserProfileToUI(user) {
    if (!user) return;
    if (DOM.topUserName) DOM.topUserName.textContent = user.full_name || 'Muhammad Saad';
    if (DOM.topUserRole) DOM.topUserRole.textContent = user.role || 'Lead Financial Controller';
    if (DOM.userAvatarText) {
        const initials = (user.full_name || 'MH').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        DOM.userAvatarText.textContent = initials;
    }
    if (DOM.headerCompanyName) {
        const displayName = (user.company_name && user.company_name.trim()) ? user.company_name.trim() : 'Tri Agro Farms';
        DOM.headerCompanyName.innerHTML = `${displayName} <span class="currency-badge">PKR</span>`;
    }
    if (DOM.headerCompanyAddress) {
        const parts = [user.address, user.phone].filter(Boolean);
        DOM.headerCompanyAddress.textContent = parts.join(' | ');
    }
    const slipCompany = document.getElementById('slipCompanyName');
    if (slipCompany && user.company_name) slipCompany.textContent = user.company_name;
    const slipPrep = document.getElementById('slipPreparedBy');
    if (slipPrep && user.full_name) slipPrep.textContent = user.full_name;

    // Pre-fill settings form
    if (DOM.setFullName) DOM.setFullName.value = user.full_name || '';
    if (DOM.setEmail) DOM.setEmail.value = user.email || '';
    if (DOM.setCompanyName) DOM.setCompanyName.value = user.company_name || '';
    if (DOM.setPhone) DOM.setPhone.value = user.phone || '';
    if (DOM.setAddress) DOM.setAddress.value = user.address || '';
}

// ---------------------------------------------------------------------------
// VIEW 1: DASHBOARD RENDERING
// ---------------------------------------------------------------------------
function renderDashboardKPIs(data) {
    const received = data.amount_received_pkr || 0;
    const expense = data.total_expense_pkr || 0;
    const netDiff = data.net_received_minus_expense_pkr !== undefined 
        ? data.net_received_minus_expense_pkr 
        : (received - expense);

    // 3 Primary Executive KPIs: Total Income, Expenses, Remaining Amt After All Expenses
    if (DOM.kpiTotalIncome) {
        DOM.kpiTotalIncome.textContent = formatPKR(received);
    }
    if (DOM.kpiAmountReceived) {
        DOM.kpiAmountReceived.textContent = formatPKR(received);
    }
    if (DOM.kpiTotalExpenses) {
        DOM.kpiTotalExpenses.textContent = formatPKR(expense);
    }
    if (DOM.kpiRemainingAmt) {
        DOM.kpiRemainingAmt.textContent = formatPKR(netDiff);
        DOM.kpiRemainingAmt.style.color = netDiff >= 0 ? '#059669' : '#DC2626';
    }
    if (DOM.cardRemainingAmt) {
        DOM.cardRemainingAmt.style.borderLeftColor = netDiff >= 0 ? '#059669' : '#DC2626';
    }
    if (DOM.kpiNetReceivedMinusExpense) {
        DOM.kpiNetReceivedMinusExpense.textContent = formatPKR(netDiff);
        DOM.kpiNetReceivedMinusExpense.style.color = netDiff >= 0 ? '#059669' : '#DC2626';
    }
    if (DOM.cardNetReceivedMinusExpense) {
        DOM.cardNetReceivedMinusExpense.style.borderLeftColor = netDiff >= 0 ? '#059669' : '#DC2626';
    }

    if (DOM.kpiLiquidFunds) DOM.kpiLiquidFunds.textContent = formatPKR(data.liquid_funds_pkr);
    if (DOM.kpiReceivables) DOM.kpiReceivables.textContent = formatPKR(data.receivables_pkr);
    if (DOM.kpiPayables) DOM.kpiPayables.textContent = formatPKR(data.payables_pkr);
    if (DOM.kpiWorkingCapital) DOM.kpiWorkingCapital.textContent = formatPKR(data.working_capital_pkr);

    DOM.statGrossRevenue.textContent = formatPKR(data.total_revenue_pkr);
    DOM.statTotalExpense.textContent = formatPKR(data.total_expense_pkr);
    DOM.statNetProfit.textContent = formatPKR(data.net_profit_pkr);

    if (DOM.statNetReceivedMinusExpense) {
        DOM.statNetReceivedMinusExpense.textContent = formatPKR(netDiff);
        DOM.statNetReceivedMinusExpense.style.color = netDiff >= 0 ? '#059669' : '#DC2626';
    }

    if (DOM.stripNetReceivedMinusExpense) {
        DOM.stripNetReceivedMinusExpense.textContent = formatPKR(netDiff);
        DOM.stripNetReceivedMinusExpense.style.color = netDiff >= 0 ? '#059669' : '#DC2626';
    }

    const margin = data.total_revenue_pkr > 0 
        ? ((data.net_profit_pkr / data.total_revenue_pkr) * 100).toFixed(1) + '%' 
        : '0%';
    DOM.statNetMargin.textContent = margin;
}

function renderCashFlowChart(flowData) {
    if (!DOM.cashFlowChartWrap) return;
    DOM.cashFlowChartWrap.innerHTML = '';

    // Calculate total Inflow and Outflow from live database summary metrics
    let totalInflow = 0;
    let totalOutflow = 0;

    if (STATE.summary) {
        totalInflow = Number(STATE.summary.amount_received_pkr || STATE.summary.total_revenue_pkr || 0);
        totalOutflow = Number(STATE.summary.total_expense_pkr || 0);
    }

    if (totalInflow === 0 && totalOutflow === 0 && Array.isArray(flowData) && flowData.length > 0) {
        flowData.forEach(d => {
            totalInflow += (Number(d.inflow_pkr) || 0);
            totalOutflow += (Number(d.outflow_pkr) || 0);
        });
    }

    const totalCashActivity = totalInflow + totalOutflow;

    if (totalCashActivity <= 0) {
        DOM.cashFlowChartWrap.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 180px; color: var(--text-muted); text-align: center; margin: auto;">
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.4; margin-bottom: 0.5rem;"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>
                <div style="font-size: 0.9rem; font-weight: 600;">No Cash Flow Activity Recorded</div>
                <div style="font-size: 0.78rem; opacity: 0.8;">Record customer receipts, income, or expenses to view Pie Chart</div>
            </div>
        `;
        return;
    }

    const pctInflow = ((totalInflow / totalCashActivity) * 100).toFixed(1);
    const pctOutflow = (100 - parseFloat(pctInflow)).toFixed(1);
    const netFlow = totalInflow - totalOutflow;

    const r = 65;
    const C = 2 * Math.PI * r;
    const inflowStroke = ((totalInflow / totalCashActivity) * C).toFixed(2);

    DOM.cashFlowChartWrap.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; gap: 2rem; flex-wrap: wrap; width: 100%; padding: 0.75rem 0;">
            <!-- Interactive SVG Pie / Donut Chart -->
            <div style="position: relative; width: 180px; height: 180px; flex-shrink: 0;">
                <svg viewBox="0 0 200 200" width="180" height="180" style="transform: rotate(-90deg); filter: drop-shadow(0 4px 8px rgba(0,0,0,0.06));">
                    <!-- Base ring -->
                    <circle cx="100" cy="100" r="${r}" fill="none" stroke="#F1F5F9" stroke-width="42"></circle>
                    <!-- Outflow Slice (Red) -->
                    <circle cx="100" cy="100" r="${r}" fill="none" stroke="#EF4444" stroke-width="42"
                        stroke-dasharray="${C.toFixed(2)} ${C.toFixed(2)}"
                        stroke-dashoffset="0"></circle>
                    <!-- Inflow Slice (Green) -->
                    <circle cx="100" cy="100" r="${r}" fill="none" stroke="#10B981" stroke-width="42"
                        stroke-dasharray="${inflowStroke} ${C.toFixed(2)}"
                        stroke-dashoffset="0"></circle>
                </svg>
                <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; pointer-events: none; text-align: center;">
                    <span style="font-size: 0.7rem; color: #64748B; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Net Flow</span>
                    <span style="font-size: 0.92rem; font-weight: 800; color: ${netFlow >= 0 ? '#059669' : '#DC2626'};">${formatPKR(netFlow)}</span>
                </div>
            </div>

            <!-- Financial Distribution Details -->
            <div style="display: flex; flex-direction: column; gap: 0.65rem; min-width: 220px; flex: 1; max-width: 320px;">
                <div style="background: #ECFDF5; border: 1.5px solid #A7F3D0; padding: 0.65rem 0.9rem; border-radius: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.82rem; font-weight: 700; color: #065F46;">🟢 Cash Inflow</span>
                        <span style="font-size: 0.78rem; font-weight: 800; color: #047857; background: #D1FAE5; padding: 2px 7px; border-radius: 12px;">${pctInflow}%</span>
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #064E3B; margin-top: 3px;">${formatPKR(totalInflow)}</div>
                </div>

                <div style="background: #FEF2F2; border: 1.5px solid #FECACA; padding: 0.65rem 0.9rem; border-radius: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.82rem; font-weight: 700; color: #991B1B;">🔴 Cash Outflow</span>
                        <span style="font-size: 0.78rem; font-weight: 800; color: #B91C1C; background: #FEE2E2; padding: 2px 7px; border-radius: 12px;">${pctOutflow}%</span>
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #7F1D1D; margin-top: 3px;">${formatPKR(totalOutflow)}</div>
                </div>
            </div>
        </div>
    `;
}

function renderRecentVouchers(recentList) {
    DOM.recentVouchersTableBody.innerHTML = '';
    if (!recentList || recentList.length === 0) {
        DOM.recentVouchersTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 1.5rem;">No recent transactions. Click "+ Record Transaction" to create one.</td></tr>';
        return;
    }

    recentList.slice(0, 7).forEach(v => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${v.voucher_number}</strong></td>
            <td>${formatDate(v.date)}</td>
            <td><span class="badge ${getVoucherBadgeClass(v.voucher_type)}">${v.voucher_type}</span></td>
            <td>${v.reference_no || '-'}</td>
            <td>${v.narration || '-'}</td>
            <td class="table-amount">${formatPKR(v.total_amount)}</td>
            <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="viewVoucherSlip(${v.id})" title="View Voucher Slip">Inspect</button>
                <button type="button" class="btn btn-sm" onclick="deleteVoucher(${v.id}, '${v.voucher_number}')" title="Delete Voucher" style="margin-left: 4px; background: #EF4444; color: #fff; border: 1px solid #DC2626; padding: 4px 8px; border-radius: 4px; cursor: pointer;">Delete</button>
            </td>
        `;
        DOM.recentVouchersTableBody.appendChild(tr);
    });
}

function getVoucherBadgeClass(vType) {
    const t = (vType || '').toLowerCase();
    if (t.includes('receipt') || t === 'cr') return 'badge-cr';
    if (t.includes('payment') || t === 'cp') return 'badge-cp';
    if (t.includes('bank receipt') || t === 'br') return 'badge-br';
    if (t.includes('bank payment') || t === 'bp') return 'badge-bp';
    if (t.includes('sales') || t === 'sv') return 'badge-sv';
    if (t.includes('purchase') || t === 'pv') return 'badge-pv';
    return 'badge-jv';
}

// ---------------------------------------------------------------------------
// VIEW 2: VOUCHER REGISTER
// ---------------------------------------------------------------------------
function renderVouchersTable() {
    const activeTab = DOM.voucherFilterTabs.querySelector('.filter-tab.active');
    const filterType = activeTab ? activeTab.getAttribute('data-vtype') : '';
    const query = (DOM.voucherSearchInput.value || '').toLowerCase().trim();

    let filtered = STATE.vouchers;
    if (filterType) {
        filtered = filtered.filter(v => (v.voucher_type || '').toLowerCase().includes(filterType.toLowerCase()));
    }
    if (query) {
        filtered = filtered.filter(v => 
            (v.voucher_number || '').toLowerCase().includes(query) ||
            (v.reference_no || '').toLowerCase().includes(query) ||
            (v.narration || '').toLowerCase().includes(query)
        );
    }

    DOM.vouchersListBody.innerHTML = '';
    if (filtered.length === 0) {
        DOM.vouchersListBody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem;">No matching voucher records found.</td></tr>';
        return;
    }

    filtered.forEach(v => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${v.voucher_number}</strong></td>
            <td>${formatDate(v.date)}</td>
            <td><span class="badge ${getVoucherBadgeClass(v.voucher_type)}">${v.voucher_type}</span></td>
            <td>${v.reference_no || '-'}</td>
            <td>${v.narration || '-'}</td>
            <td>${v.created_by || 'Admin'}</td>
            <td class="table-amount">${formatPKR(v.total_amount)}</td>
            <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="viewVoucherSlip(${v.id})" title="View Voucher Slip">View Slip</button>
                <button type="button" class="btn btn-sm" onclick="deleteVoucher(${v.id}, '${v.voucher_number}')" title="Delete Voucher" style="margin-left: 4px; background: #EF4444; color: #fff; border: 1px solid #DC2626; padding: 4px 8px; border-radius: 4px; cursor: pointer;">Delete</button>
            </td>
        `;
        DOM.vouchersListBody.appendChild(tr);
    });
}

// ---------------------------------------------------------------------------
// VIEW 3: CHART OF ACCOUNTS
// ---------------------------------------------------------------------------
function renderAccountsTable() {
    const activeTab = DOM.accountTypeTabs.querySelector('.filter-tab.active');
    const filterType = activeTab ? activeTab.getAttribute('data-atype') : '';
    const query = (DOM.accountSearchInput.value || '').toLowerCase().trim();

    let filtered = STATE.accounts;
    if (filterType) {
        filtered = filtered.filter(a => a.type.toLowerCase() === filterType.toLowerCase());
    }
    if (query) {
        filtered = filtered.filter(a => 
            a.code.toLowerCase().includes(query) ||
            a.name.toLowerCase().includes(query) ||
            (a.description || '').toLowerCase().includes(query)
        );
    }

    DOM.accountsTableBody.innerHTML = '';
    if (filtered.length === 0) {
        DOM.accountsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem;">No accounts match your criteria.</td></tr>';
        return;
    }

    filtered.forEach(a => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><code>${a.code}</code></td>
            <td><strong>${a.name}</strong></td>
            <td><span class="badge badge-${a.type.toLowerCase()}">${a.type}</span></td>
            <td>${a.description || '-'}</td>
            <td class="table-amount">${formatPKR(a.balance)}</td>
            <td style="text-align: center;">
                <span class="badge" style="background: #ECFDF5; color: #059669;">Active</span>
            </td>
            <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="inspectAccountGl(${a.id})" title="View Ledger">Ledger</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="openAccountModal(${a.id})" title="Edit Account" style="margin-left: 4px;">Edit</button>
                <button type="button" class="btn btn-sm" onclick="deleteAccount(${a.id}, '${(a.name || '').replace(/'/g, "\\'")}')" title="Delete Account" style="margin-left: 4px; background: #EF4444; color: #fff; border: 1px solid #DC2626; padding: 4px 8px; border-radius: 4px; cursor: pointer;">Delete</button>
            </td>
        `;
        DOM.accountsTableBody.appendChild(tr);
    });
}

function inspectAccountGl(accId) {
    switchView('reportsView');
    switchReportSubView('generalLedger');
    if (DOM.glAccountSelect) {
        DOM.glAccountSelect.value = accId;
        loadGeneralLedgerStatement();
    }
}

// ---------------------------------------------------------------------------
// VIEW 4: COMMERCIAL PARTIES (CUSTOMERS & VENDORS)
// ---------------------------------------------------------------------------
function renderPartiesTable() {
    const activeTab = DOM.partyFilterTabs.querySelector('.filter-tab.active');
    const filterType = activeTab ? activeTab.getAttribute('data-ptype') : '';
    const query = (DOM.partySearchInput.value || '').toLowerCase().trim();

    let filtered = STATE.parties;
    if (filterType) {
        filtered = filtered.filter(p => p.type.toLowerCase() === filterType.toLowerCase());
    }
    if (query) {
        filtered = filtered.filter(p => 
            p.name.toLowerCase().includes(query) ||
            (p.contact_person || '').toLowerCase().includes(query) ||
            (p.city || '').toLowerCase().includes(query) ||
            (p.phone || '').toLowerCase().includes(query)
        );
    }

    // Update Summary Metrics
    const totalRec = STATE.parties.filter(p => p.type === 'Customer').reduce((s, p) => s + p.current_balance, 0);
    const totalPay = STATE.parties.filter(p => p.type === 'Vendor').reduce((s, p) => s + p.current_balance, 0);
    DOM.partyTotalReceivable.textContent = formatPKR(totalRec);
    DOM.partyTotalPayable.textContent = formatPKR(totalPay);

    DOM.partiesTableBody.innerHTML = '';
    if (filtered.length === 0) {
        DOM.partiesTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem;">No commercial parties registered yet.</td></tr>';
        return;
    }

    filtered.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${p.name}</strong></td>
            <td><span class="badge badge-${p.type.toLowerCase()}">${p.type}</span></td>
            <td>${p.contact_person || '-'}</td>
            <td>${p.phone || '-'}</td>
            <td>${p.city || '-'}<br><small style="color: var(--text-muted);">${p.address || ''}</small></td>
            <td class="table-amount">${formatPKR(p.credit_limit)}</td>
            <td class="table-amount">${formatPKR(p.current_balance)}</td>
            <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="openPartyModal(${p.id})" title="Edit Party">Edit</button>
                <button type="button" class="btn btn-primary btn-sm" onclick="inspectPartyStatement(${p.id})" title="Statement" style="margin-left: 4px;">Statement</button>
                <button type="button" class="btn btn-sm" onclick="deleteParty(${p.id}, '${(p.name || '').replace(/'/g, "\\'")}')" title="Delete Party" style="margin-left: 4px; background: #EF4444; color: #fff; border: 1px solid #DC2626; padding: 4px 8px; border-radius: 4px; cursor: pointer;">Delete</button>
            </td>
        `;
        DOM.partiesTableBody.appendChild(tr);
    });
}

function inspectPartyStatement(partyId) {
    switchView('reportsView');
    switchReportSubView('partyLedger');
    if (DOM.partyStatementSelect) {
        DOM.partyStatementSelect.value = partyId;
        loadPartyStatement();
    }
}

// ---------------------------------------------------------------------------
// VIEW 5: FINANCIAL REPORTS
// ---------------------------------------------------------------------------
async function loadTrialBalanceReport() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/reports/trial-balance`);
        if (!res.ok) throw new Error('Trial balance error');
        const data = await res.json();

        DOM.trialBalanceTableBody.innerHTML = '';
        data.items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code>${item.account_code}</code></td>
                <td><strong>${item.account_name}</strong></td>
                <td><span class="badge badge-${item.account_type.toLowerCase()}">${item.account_type}</span></td>
                <td class="table-amount">${item.debit_pkr > 0 ? formatPKR(item.debit_pkr) : '-'}</td>
                <td class="table-amount">${item.credit_pkr > 0 ? formatPKR(item.credit_pkr) : '-'}</td>
            `;
            DOM.trialBalanceTableBody.appendChild(tr);
        });

        DOM.trialBalanceTableFoot.innerHTML = `
            <tr>
                <td colspan="3" style="text-align: right; padding: 0.85rem 1rem;">Grand Totals (PKR):</td>
                <td class="table-amount" style="color: #059669; font-size: 1.05rem;">${formatPKR(data.total_debit_pkr)}</td>
                <td class="table-amount" style="color: #2563EB; font-size: 1.05rem;">${formatPKR(data.total_credit_pkr)}</td>
            </tr>
        `;

        if (data.is_balanced) {
            DOM.trialBalanceStatusBadge.className = 'diff-badge balanced';
            DOM.trialBalanceStatusBadge.textContent = '✓ Perfectly Balanced (Difference: PKR 0.00)';
        } else {
            DOM.trialBalanceStatusBadge.className = 'diff-badge unbalanced';
            DOM.trialBalanceStatusBadge.textContent = `⚠ Out of Balance (Difference: ${formatPKR(data.difference_pkr)})`;
        }
    } catch (err) {
        console.error('loadTrialBalanceReport error:', err);
    }
}

async function loadProfitLossReport() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/reports/profit-loss`);
        if (!res.ok) throw new Error('Profit loss error');
        const data = await res.json();

        DOM.plRevenuesTable.querySelector('tbody').innerHTML = '';
        data.revenues.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${r.code} - ${r.name}</td><td class="table-amount">${formatPKR(r.amount_pkr)}</td>`;
            DOM.plRevenuesTable.querySelector('tbody').appendChild(tr);
        });
        const revTotalTr = document.createElement('tr');
        revTotalTr.style.fontWeight = '800';
        revTotalTr.innerHTML = `<td>Total Operating Revenues</td><td class="table-amount" style="color: #059669;">${formatPKR(data.total_revenue_pkr)}</td>`;
        DOM.plRevenuesTable.querySelector('tbody').appendChild(revTotalTr);

        DOM.plExpensesTable.querySelector('tbody').innerHTML = '';
        data.expenses.forEach(e => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${e.code} - ${e.name}</td><td class="table-amount">${formatPKR(e.amount_pkr)}</td>`;
            DOM.plExpensesTable.querySelector('tbody').appendChild(tr);
        });
        const expTotalTr = document.createElement('tr');
        expTotalTr.style.fontWeight = '800';
        expTotalTr.innerHTML = `<td>Total Operating Expenses</td><td class="table-amount" style="color: #DC2626;">${formatPKR(data.total_expense_pkr)}</td>`;
        DOM.plExpensesTable.querySelector('tbody').appendChild(expTotalTr);

        DOM.plNetProfitSummary.textContent = formatPKR(data.net_profit_pkr);
    } catch (err) {
        console.error('loadProfitLossReport error:', err);
    }
}

function populateGlAccountDropdown() {
    if (!DOM.glAccountSelect) return;
    DOM.glAccountSelect.innerHTML = '<option value="">-- Choose General Ledger Account --</option>';
    STATE.accounts.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `${a.code} - ${a.name} (${a.type})`;
        DOM.glAccountSelect.appendChild(opt);
    });
}

async function loadGeneralLedgerStatement() {
    const accId = DOM.glAccountSelect.value;
    if (!accId) {
        alert('Please select an account first.');
        return;
    }

    const fromDate = DOM.glStatementFromDate ? DOM.glStatementFromDate.value : '';
    const toDate = DOM.glStatementToDate ? DOM.glStatementToDate.value : '';

    let url = `${API_BASE}/api/v1/reports/general-ledger/${accId}`;
    const params = [];
    if (fromDate) params.push(`from_date=${encodeURIComponent(fromDate)}`);
    if (toDate) params.push(`to_date=${encodeURIComponent(toDate)}`);
    if (params.length > 0) url += `?${params.join('&')}`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Could not load account ledger');
        const data = await res.json();

        DOM.glStatementTableBody.innerHTML = '';
        if (DOM.glStatementTableFoot) DOM.glStatementTableFoot.innerHTML = '';

        if (!data.statement || data.statement.length === 0) {
            DOM.glStatementTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 1.5rem;">No transactions posted for this account in the selected period.</td></tr>';
            return;
        }

        let totDebit = 0;
        let totCredit = 0;

        data.statement.forEach(row => {
            totDebit += (row.debit_pkr || 0);
            totCredit += (row.credit_pkr || 0);
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.date}</td>
                <td><strong><a href="#" style="color: var(--navy-700);" onclick="viewVoucherSlip(${row.voucher_id}); return false;">${row.voucher_number}</a></strong></td>
                <td>${escapeHtml(row.narration || '-')}</td>
                <td class="table-amount" style="color: #059669;">${row.debit_pkr > 0 ? formatPKR(row.debit_pkr) : '-'}</td>
                <td class="table-amount" style="color: #DC2626;">${row.credit_pkr > 0 ? formatPKR(row.credit_pkr) : '-'}</td>
                <td class="table-amount" style="font-weight: 800; color: var(--navy-900);">${formatPKR(row.running_balance_pkr)}</td>
            `;
            DOM.glStatementTableBody.appendChild(tr);
        });

        if (DOM.glStatementTableFoot) {
            const finalBal = data.statement[data.statement.length - 1].running_balance_pkr;
            DOM.glStatementTableFoot.innerHTML = `
                <tr>
                    <td colspan="3" style="text-align: right; padding: 0.85rem 1rem;">Statement Totals &amp; Closing Balance:</td>
                    <td class="table-amount" style="color: #059669; font-size: 1rem;">${formatPKR(totDebit)}</td>
                    <td class="table-amount" style="color: #DC2626; font-size: 1rem;">${formatPKR(totCredit)}</td>
                    <td class="table-amount" style="color: var(--navy-950); font-size: 1.05rem;">${formatPKR(finalBal)}</td>
                </tr>
            `;
        }
    } catch (err) {
        console.error('loadGeneralLedgerStatement error:', err);
    }
}

function populatePartyDropdown() {
    if (!DOM.partyStatementSelect) return;
    DOM.partyStatementSelect.innerHTML = '<option value="">-- Choose Commercial Customer, Vendor or Supplier --</option>';
    STATE.parties.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.name} [${p.type}] - ${p.city || 'Pakistan'}`;
        DOM.partyStatementSelect.appendChild(opt);
    });
}

async function loadPartyStatement() {
    const partyId = DOM.partyStatementSelect.value;
    if (!partyId) {
        alert('Please select a customer, vendor or supplier first.');
        return;
    }

    const fromDate = DOM.partyStatementFromDate ? DOM.partyStatementFromDate.value : '';
    const toDate = DOM.partyStatementToDate ? DOM.partyStatementToDate.value : '';

    let url = `${API_BASE}/api/v1/reports/party-statement/${partyId}`;
    const params = [];
    if (fromDate) params.push(`from_date=${encodeURIComponent(fromDate)}`);
    if (toDate) params.push(`to_date=${encodeURIComponent(toDate)}`);
    if (params.length > 0) url += `?${params.join('&')}`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Could not load party statement');
        const data = await res.json();

        DOM.partyStatementInfoCard.style.display = 'block';
        DOM.psiName.textContent = data.party_name + ` [${data.party_type}]`;
        DOM.psiContact.textContent = 'Contact: ' + (data.contact_person || 'N/A');
        DOM.psiPhone.textContent = 'Phone: ' + (data.phone || 'N/A');
        DOM.psiBalance.textContent = formatPKR(data.current_balance_pkr);

        DOM.partyStatementTableBody.innerHTML = '';
        if (DOM.partyStatementTableFoot) DOM.partyStatementTableFoot.innerHTML = '';

        // Add Opening Balance row if exists
        const openBal = data.opening_balance_pkr || 0;
        const openTr = document.createElement('tr');
        openTr.style.background = '#F8FAFC';
        openTr.innerHTML = `
            <td><em>Initial</em></td>
            <td>—</td>
            <td><span class="badge" style="background: #E2E8F0; color: #475569;">Opening</span></td>
            <td><em>Opening Balance Carried Forward</em></td>
            <td class="table-amount">—</td>
            <td class="table-amount">—</td>
            <td class="table-amount" style="font-weight: 700; color: var(--navy-900);">${formatPKR(openBal)}</td>
        `;
        DOM.partyStatementTableBody.appendChild(openTr);

        if (!data.statement || data.statement.length === 0) {
            const noTr = document.createElement('tr');
            noTr.innerHTML = '<td colspan="7" style="text-align: center; padding: 1.5rem; color: var(--text-muted);">No new transactions posted for this party in the selected period.</td>';
            DOM.partyStatementTableBody.appendChild(noTr);
            return;
        }

        let totDeb = 0;
        let totCred = 0;

        data.statement.forEach(row => {
            totDeb += (row.debit_pkr || 0);
            totCred += (row.credit_pkr || 0);
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.date}</td>
                <td><strong><a href="#" style="color: var(--navy-700);" onclick="viewVoucherSlip(${row.voucher_id}); return false;">${row.voucher_number}</a></strong></td>
                <td><span class="badge ${getVoucherBadgeClass(row.voucher_type)}">${row.voucher_type}</span></td>
                <td>${escapeHtml(row.narration || '-')}</td>
                <td class="table-amount" style="color: #059669;">${row.debit_pkr > 0 ? formatPKR(row.debit_pkr) : '-'}</td>
                <td class="table-amount" style="color: #DC2626;">${row.credit_pkr > 0 ? formatPKR(row.credit_pkr) : '-'}</td>
                <td class="table-amount" style="font-weight: 800; color: var(--navy-900);">${formatPKR(row.running_balance_pkr)}</td>
            `;
            DOM.partyStatementTableBody.appendChild(tr);
        });

        if (DOM.partyStatementTableFoot) {
            const closingBal = data.closing_balance_pkr !== undefined 
                ? data.closing_balance_pkr 
                : (data.statement.length > 0 ? data.statement[data.statement.length - 1].running_balance_pkr : openBal);
            DOM.partyStatementTableFoot.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: right; padding: 0.85rem 1rem;">Statement Total Debit &amp; Credit:</td>
                    <td class="table-amount" style="color: #059669; font-size: 1rem;">${formatPKR(totDeb)}</td>
                    <td class="table-amount" style="color: #DC2626; font-size: 1rem;">${formatPKR(totCred)}</td>
                    <td class="table-amount" style="color: var(--navy-950); font-size: 1.05rem;">${formatPKR(closingBal)}</td>
                </tr>
            `;
        }
    } catch (err) {
        console.error('loadPartyStatement error:', err);
    }
}

// ---------------------------------------------------------------------------
// ANNUAL REPORT (Whole Year)
// ---------------------------------------------------------------------------
function initAnnualReportControls() {
    if (!DOM.annualYearSelect || DOM.annualYearSelect.children.length > 0) return;
    const currentYear = new Date().getFullYear();
    const years = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1];
    years.forEach(y => {
        const opt = document.createElement('option');
        opt.value = y;
        opt.textContent = `Fiscal Year ${y}`;
        if (y === currentYear) opt.selected = true;
        DOM.annualYearSelect.appendChild(opt);
    });
}

async function loadAnnualReport() {
    initAnnualReportControls();
    const year = DOM.annualYearSelect ? DOM.annualYearSelect.value : new Date().getFullYear();

    DOM.annualReportTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: var(--text-muted);">Compiling Annual Financial Report for ' + year + '...</td></tr>';

    try {
        const res = await fetch(`${API_BASE}/api/v1/reports/annual-report?year=${year}`);
        if (!res.ok) throw new Error('Failed to load annual report');
        const data = await res.json();

        // 1. KPI Strip
        if (DOM.annualKpiStrip) {
            DOM.annualKpiStrip.style.display = 'flex';
            DOM.annualTotalInflow.textContent = formatPKR(data.grand_inflow_pkr);
            DOM.annualTotalOutflow.textContent = formatPKR(data.grand_outflow_pkr);
            DOM.annualNetCash.textContent = formatPKR(data.grand_net_pkr);
            DOM.annualVoucherCount.textContent = data.grand_voucher_count;
        }

        // 2. Net Profit Banner
        if (DOM.annualProfitBanner) {
            DOM.annualProfitBanner.style.display = 'flex';
            DOM.annualNetProfit.textContent = formatPKR(data.net_profit_pkr);
            DOM.annualRevenue.textContent = formatPKR(data.total_revenue_pkr);
            DOM.annualExpense.textContent = formatPKR(data.total_expense_pkr);
        }

        // 3. 12-Month Table
        DOM.annualReportTableBody.innerHTML = '';
        data.months.forEach(m => {
            const tr = document.createElement('tr');
            const netColor = m.net_pkr >= 0 ? '#059669' : '#DC2626';
            tr.innerHTML = `
                <td><strong>${m.month_name}</strong></td>
                <td class="table-amount" style="color: ${m.inflow_pkr > 0 ? '#059669' : 'inherit'};">${m.inflow_pkr > 0 ? formatPKR(m.inflow_pkr) : '-'}</td>
                <td class="table-amount" style="color: ${m.outflow_pkr > 0 ? '#DC2626' : 'inherit'};">${m.outflow_pkr > 0 ? formatPKR(m.outflow_pkr) : '-'}</td>
                <td class="table-amount" style="color: var(--text-muted);">${m.journal_pkr > 0 ? formatPKR(m.journal_pkr) : '-'}</td>
                <td class="table-amount" style="font-weight: 700; color: ${netColor};">${formatPKR(m.net_pkr)}</td>
                <td style="text-align: center;"><span class="badge ${m.voucher_count > 0 ? 'badge-primary' : 'badge-secondary'}">${m.voucher_count} vouchers</span></td>
            `;
            DOM.annualReportTableBody.appendChild(tr);
        });

        // 4. Grand Totals Foot
        const grandNetColor = data.grand_net_pkr >= 0 ? '#059669' : '#DC2626';
        DOM.annualReportTableFoot.innerHTML = `
            <tr>
                <td style="padding: 0.85rem 1rem;">Whole Year ${year} Totals:</td>
                <td class="table-amount" style="color: #059669; font-size: 1.05rem;">${formatPKR(data.grand_inflow_pkr)}</td>
                <td class="table-amount" style="color: #DC2626; font-size: 1.05rem;">${formatPKR(data.grand_outflow_pkr)}</td>
                <td class="table-amount" style="color: var(--text-muted); font-size: 1.05rem;">${formatPKR(data.grand_journal_pkr)}</td>
                <td class="table-amount" style="color: ${grandNetColor}; font-size: 1.05rem;">${formatPKR(data.grand_net_pkr)}</td>
                <td style="text-align: center; font-size: 1.05rem;">${data.grand_voucher_count}</td>
            </tr>
        `;

        // 5. Account Type Breakdown
        if (DOM.annualTypeSummary && data.account_type_summary) {
            DOM.annualTypeSummary.style.display = 'block';
            DOM.annualTypeSummaryBody.innerHTML = '';
            data.account_type_summary.forEach(ts => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${ts.type}</strong></td>
                    <td style="text-align: center;">${ts.account_count} accounts</td>
                    <td class="table-amount" style="font-weight: 700;">${formatPKR(ts.total_balance_pkr)}</td>
                `;
                DOM.annualTypeSummaryBody.appendChild(row);
            });
        }
    } catch (err) {
        console.error('loadAnnualReport error:', err);
        DOM.annualReportTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: #DC2626;">Error loading annual report: ${escapeHtml(err.message)}</td></tr>`;
    }
}

// ---------------------------------------------------------------------------
// MONTHLY REPORT (1 to 30 / Whole Month)
// ---------------------------------------------------------------------------
function initMonthlyReportControls() {
    if (DOM.monthlyYearSelect && DOM.monthlyYearSelect.children.length === 0) {
        const currentYear = new Date().getFullYear();
        const years = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1];
        years.forEach(y => {
            const opt = document.createElement('option');
            opt.value = y;
            opt.textContent = `${y}`;
            if (y === currentYear) opt.selected = true;
            DOM.monthlyYearSelect.appendChild(opt);
        });
    }

    if (DOM.monthlyMonthSelect && !DOM.monthlyMonthSelect.value) {
        const currentMonth = new Date().getMonth() + 1;
        DOM.monthlyMonthSelect.value = String(currentMonth);
    }
}

async function loadMonthlyReport() {
    initMonthlyReportControls();
    const year = DOM.monthlyYearSelect ? DOM.monthlyYearSelect.value : new Date().getFullYear();
    const month = DOM.monthlyMonthSelect ? DOM.monthlyMonthSelect.value : (new Date().getMonth() + 1);

    DOM.monthlyReportTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: var(--text-muted);">Loading monthly transactions (Day 1 to 30/31)...</td></tr>';

    try {
        const res = await fetch(`${API_BASE}/api/v1/reports/monthly-report?year=${year}&month=${month}`);
        if (!res.ok) throw new Error('Failed to load monthly report');
        const data = await res.json();

        // 1. Period Banner
        if (DOM.monthlyPeriodBanner) {
            DOM.monthlyPeriodBanner.style.display = 'block';
            DOM.monthlyPeriodTitle.textContent = `${data.month_name} ${year} Monthly Report (${data.period})`;
        }

        // 2. KPI Strip
        if (DOM.monthlyKpiStrip) {
            DOM.monthlyKpiStrip.style.display = 'flex';
            DOM.monthlyTotalInflow.textContent = formatPKR(data.total_inflow_pkr);
            DOM.monthlyTotalOutflow.textContent = formatPKR(data.total_outflow_pkr);
            DOM.monthlyNetCash.textContent = formatPKR(data.net_pkr);
            DOM.monthlyVoucherCount.textContent = data.voucher_count;
        }

        // 3. Type Breakdown Badges
        if (DOM.monthlyTypeBreakdown && data.type_breakdown) {
            DOM.monthlyTypeBreakdown.style.display = 'flex';
            DOM.monthlyTypeBreakdown.innerHTML = '';
            data.type_breakdown.forEach(tb => {
                const badge = document.createElement('div');
                badge.className = 'kpi-card';
                badge.style.padding = '0.5rem 0.85rem';
                badge.style.fontSize = '0.82rem';
                badge.style.flex = '1 1 140px';
                badge.innerHTML = `
                    <div style="font-weight: 600; color: var(--text-secondary);">${tb.type} (${tb.count})</div>
                    <div style="font-weight: 800; font-size: 1rem; color: var(--navy-900); margin-top: 2px;">${formatPKR(tb.total_pkr)}</div>
                `;
                DOM.monthlyTypeBreakdown.appendChild(badge);
            });
        }

        // 4. Vouchers Table Body
        DOM.monthlyReportTableBody.innerHTML = '';
        if (!data.vouchers || data.vouchers.length === 0) {
            DOM.monthlyReportTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: var(--text-muted);">No vouchers recorded for 1 to 30 ${data.month_name} ${year}.</td></tr>`;
        } else {
            data.vouchers.forEach(v => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${v.date}</td>
                    <td><a href="#" style="font-weight: 700; color: var(--navy-700);" onclick="viewVoucherSlip(${v.id}); return false;">${v.voucher_number}</a></td>
                    <td><span class="badge ${getVoucherBadgeClass(v.voucher_type)}">${v.voucher_type}</span></td>
                    <td>${escapeHtml(v.reference_no || '-')}</td>
                    <td>${escapeHtml(v.narration || '-')}</td>
                    <td class="table-amount" style="font-weight: 700;">${formatPKR(v.total_amount)}</td>
                `;
                DOM.monthlyReportTableBody.appendChild(tr);
            });
        }

        // 5. Table Foot
        const netColor = data.net_pkr >= 0 ? '#059669' : '#DC2626';
        DOM.monthlyReportTableFoot.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: right; padding: 0.85rem 1rem;">Total Inflow: <strong style="color: #059669;">${formatPKR(data.total_inflow_pkr)}</strong> &bull; Total Outflow: <strong style="color: #DC2626;">${formatPKR(data.total_outflow_pkr)}</strong></td>
                <td style="text-align: right; padding: 0.85rem 1rem;">Net (1 to 30):</td>
                <td class="table-amount" style="font-size: 1.05rem; color: ${netColor};">${formatPKR(data.net_pkr)}</td>
            </tr>
        `;

        // 6. Daily Summary (1 to 30 days)
        if (DOM.monthlyDailySummaryWrap && data.daily_summary) {
            DOM.monthlyDailySummaryWrap.style.display = data.daily_summary.length > 0 ? 'block' : 'none';
            DOM.monthlyDailySummaryBody.innerHTML = '';
            data.daily_summary.forEach(d => {
                const dRow = document.createElement('tr');
                dRow.innerHTML = `
                    <td><strong>${d.date}</strong></td>
                    <td class="table-amount" style="color: ${d.inflow_pkr > 0 ? '#059669' : 'inherit'};">${d.inflow_pkr > 0 ? formatPKR(d.inflow_pkr) : '-'}</td>
                    <td class="table-amount" style="color: ${d.outflow_pkr > 0 ? '#DC2626' : 'inherit'};">${d.outflow_pkr > 0 ? formatPKR(d.outflow_pkr) : '-'}</td>
                    <td class="table-amount" style="color: var(--text-muted);">${d.journal_pkr > 0 ? formatPKR(d.journal_pkr) : '-'}</td>
                    <td style="text-align: center;"><span class="badge badge-secondary">${d.count} tx</span></td>
                `;
                DOM.monthlyDailySummaryBody.appendChild(dRow);
            });
        }

    } catch (err) {
        console.error('loadMonthlyReport error:', err);
        DOM.monthlyReportTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: #DC2626;">Error loading monthly report: ${escapeHtml(err.message)}</td></tr>`;
    }
}

// ---------------------------------------------------------------------------
// VIEW 6: COMPANY & PROFILE SETTINGS (Edit Profile)
// ---------------------------------------------------------------------------
async function handleProfileUpdate(e) {
    e.preventDefault();

    const fullName = DOM.setFullName.value.trim();
    const email = DOM.setEmail.value.trim();
    const companyName = DOM.setCompanyName.value.trim();
    const phone = DOM.setPhone.value.trim();
    const address = DOM.setAddress.value.trim();
    const newPass = DOM.setNewPassword.value;
    const confirmPass = DOM.setConfirmPassword.value;

    if (newPass && newPass !== confirmPass) {
        showSettingsAlert('error', 'New passwords do not match. Please verify.');
        return;
    }

    if (newPass && newPass.length < 6) {
        showSettingsAlert('error', 'New password must contain at least 6 characters.');
        return;
    }

    const payload = {
        full_name: fullName,
        email: email,
        company_name: companyName,
        phone: phone,
        address: address
    };
    if (newPass) payload.password = newPass;

    try {
        const res = await fetch(`${API_BASE}/api/v1/auth/profile`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to update profile.');
        }

        const updatedUser = await res.json();
        STATE.profile = updatedUser;
        applyUserProfileToUI(updatedUser);

        // Keep local and session storage synchronized with new credentials
        if (updatedUser.access_token) {
            sessionStorage.setItem('ledger_access_token', updatedUser.access_token);
        }
        if (updatedUser.email) {
            sessionStorage.setItem('ledger_user_email', updatedUser.email);
            try {
                localStorage.setItem('ledger_remembered_username', updatedUser.email);
            } catch (e) {}
        }

        DOM.setNewPassword.value = '';
        DOM.setConfirmPassword.value = '';
        showSettingsAlert('success', '✓ Profile & Company Details successfully saved and updated in database!');
    } catch (err) {
        showSettingsAlert('error', err.message || 'Error updating settings.');
    }
}

function showSettingsAlert(type, message) {
    DOM.settingsAlertBanner.style.display = 'block';
    DOM.settingsAlertBanner.className = `diff-badge ${type === 'success' ? 'balanced' : 'unbalanced'}`;
    DOM.settingsAlertBanner.textContent = message;
    setTimeout(() => {
        DOM.settingsAlertBanner.style.display = 'none';
    }, 6000);
}

// ---------------------------------------------------------------------------
// VIEW 7: BACKUP & SYNC
// ---------------------------------------------------------------------------
function exportDatabaseJson() {
    const snapshot = {
        exportDate: new Date().toISOString(),
        currency: 'PKR',
        profile: STATE.profile,
        accounts: STATE.accounts,
        parties: STATE.parties,
        vouchers: STATE.vouchers,
        summary: STATE.summary
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(snapshot, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `ledger_backup_${new Date().toISOString().split('T')[0]}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
}

function loadOfflineQueueFromStorage() {
    try {
        const raw = localStorage.getItem('ledger_offline_queue');
        STATE.offlineQueue = raw ? JSON.parse(raw) : [];
    } catch (e) {
        STATE.offlineQueue = [];
    }
    updateOfflineStatusUI();
}

function saveOfflineQueueToStorage() {
    try {
        localStorage.setItem('ledger_offline_queue', JSON.stringify(STATE.offlineQueue));
    } catch (e) {
        console.warn('Failed to save offline queue to storage:', e);
    }
    updateOfflineStatusUI();
}

function updateOfflineStatusUI() {
    const queueLen = (STATE.offlineQueue || []).length;
    if (!navigator.onLine) {
        if (DOM.systemStatusText) {
            DOM.systemStatusText.innerHTML = `Offline Cache &bull; ${queueLen} Queued`;
        }
        if (DOM.systemStatusPill) {
            DOM.systemStatusPill.style.borderColor = 'rgba(245, 158, 11, 0.6)';
        }
    } else if (queueLen > 0) {
        if (DOM.systemStatusText) {
            DOM.systemStatusText.innerHTML = `Online &bull; ${queueLen} Pending Sync`;
        }
    }
}

async function autoSyncOfflineQueue(silent = true) {
    loadOfflineQueueFromStorage();
    if (!STATE.offlineQueue || STATE.offlineQueue.length === 0) return;

    try {
        const payload = { vouchers: STATE.offlineQueue };
        const res = await fetch(`${API_BASE}/api/v1/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const data = await res.json();
            STATE.offlineQueue = [];
            saveOfflineQueueToStorage();
            if (!silent) {
                alert(`✓ Auto-Sync Complete: ${data.synced_count} vouchers synchronized to server.`);
            }
            await refreshAllData();
        }
    } catch (err) {
        console.warn('Auto-sync deferred (offline):', err);
    }
}

async function forceSyncOfflineQueue() {
    loadOfflineQueueFromStorage();
    if (STATE.offlineQueue.length === 0) {
        alert('All voucher entries are already synchronized with server database.');
        return;
    }
    try {
        const payload = { vouchers: STATE.offlineQueue };
        const res = await fetch(`${API_BASE}/api/v1/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            const resData = await res.json();
            STATE.offlineQueue = [];
            saveOfflineQueueToStorage();
            alert(`✓ Sync Successful:

${resData.synced_count} vouchers synchronized.
${resData.duplicates_skipped} duplicates safely resolved.`);
            refreshAllData();
        } else {
            const err = await res.json();
            alert('Sync failed: ' + (err.detail || 'Server error'));
        }
    } catch (err) {
        alert('Could not sync at this time (server unreachable): ' + err.message);
    }
}

// ---------------------------------------------------------------------------
// MODAL: VOUCHER CREATION & BALANCING
// ---------------------------------------------------------------------------
async function openVoucherModal() {
    DOM.voucherLinesBody.innerHTML = '';
    
    // Set default date to today if not set
    if (DOM.vFormDate && !DOM.vFormDate.value) {
        DOM.vFormDate.value = new Date().toISOString().split('T')[0];
    }

    // Fetch and assign next auto-generated sequence numbers (TA-YYYY-MMM-000001 and TA-ref-000001)
    try {
        const dateVal = DOM.vFormDate ? DOM.vFormDate.value : '';
        const res = await fetch(`${API_BASE}/api/v1/vouchers/next-sequence?date=${dateVal}`);
        if (res.ok) {
            const seq = await res.json();
            if (DOM.vFormVoucherNumber) DOM.vFormVoucherNumber.value = seq.next_voucher_number;
            if (DOM.vFormRef) {
                if (!DOM.vFormRef.value || DOM.vFormRef.value.startsWith('TA-ref-')) {
                    DOM.vFormRef.value = seq.next_reference_no;
                }
            }
        }
    } catch (err) {
        console.warn('Could not fetch next sequence:', err);
    }

    // Pre-create 2 rows (Debit and Credit)
    addVoucherLineRow('Debit');
    addVoucherLineRow('Credit');
    recalculateVoucherBalance();
    DOM.modalVoucher.removeAttribute('hidden');
}

function addVoucherLineRow(defaultType = 'Debit') {
    const tr = document.createElement('tr');

    let accOptions = '<option value="">-- Choose Account --</option>';
    STATE.accounts.forEach(a => {
        accOptions += `<option value="${a.id}">${a.code} - ${a.name}</option>`;
    });
    accOptions += '<option value="__ADD_NEW_ACC__" style="color: #059669; font-weight: 700;">+ Add New Account...</option>';

    let partyOptions = '<option value="">-- None (General) --</option>';
    STATE.parties.forEach(p => {
        partyOptions += `<option value="${p.id}">${p.name} (${p.type})</option>`;
    });
    partyOptions += '<option value="__ADD_NEW_PARTY__" style="color: #2563EB; font-weight: 700;">+ Add New Party / Customer...</option>';

    tr.innerHTML = `
        <td>
            <select class="line-input v-line-account" required>
                ${accOptions}
            </select>
        </td>
        <td>
            <select class="line-input v-line-party">
                ${partyOptions}
            </select>
        </td>
        <td>
            <select class="line-input v-line-type">
                <option value="Debit" ${defaultType === 'Debit' ? 'selected' : ''}>Debit</option>
                <option value="Credit" ${defaultType === 'Credit' ? 'selected' : ''}>Credit</option>
            </select>
        </td>
        <td>
            <input type="number" step="0.01" min="0.01" class="line-input v-line-amount" placeholder="0.00" required style="text-align: right;">
        </td>
        <td style="text-align: center;">
            <button type="button" class="btn-remove-line" title="Delete Row">&times;</button>
        </td>
    `;

    tr.querySelector('.btn-remove-line').addEventListener('click', () => {
        if (DOM.voucherLinesBody.children.length <= 2) {
            alert('A double-entry voucher must have at least 2 entries (Debit and Credit).');
            return;
        }
        tr.remove();
        recalculateVoucherBalance();
    });

    tr.querySelector('.v-line-type').addEventListener('change', recalculateVoucherBalance);
    const amtInput = tr.querySelector('.v-line-amount');
    if (amtInput) {
        amtInput.addEventListener('input', () => {
            const allRows = DOM.voucherLinesBody.querySelectorAll('tr');
            if (allRows.length >= 2 && allRows[0] === tr) {
                const secondAmt = allRows[1].querySelector('.v-line-amount');
                if (secondAmt && (!secondAmt.value || parseFloat(secondAmt.value) === 0)) {
                    secondAmt.value = amtInput.value;
                }
            }
            recalculateVoucherBalance();
        });
    }

    // Quick add listener
    const accSelect = tr.querySelector('.v-line-account');
    if (accSelect) {
        accSelect.addEventListener('change', (e) => {
            if (e.target.value === '__ADD_NEW_ACC__') {
                e.target.value = '';
                openAccountModal(null);
            }
        });
    }
    const partySelect = tr.querySelector('.v-line-party');
    if (partySelect) {
        partySelect.addEventListener('change', (e) => {
            if (e.target.value === '__ADD_NEW_PARTY__') {
                e.target.value = '';
                openPartyModal(null);
            }
        });
    }

    DOM.voucherLinesBody.appendChild(tr);
}

function recalculateVoucherBalance() {
    let totalDebit = 0;
    let totalCredit = 0;

    const rows = DOM.voucherLinesBody.querySelectorAll('tr');
    rows.forEach(tr => {
        const typeSelect = tr.querySelector('.v-line-type');
        const amountInput = tr.querySelector('.v-line-amount');
        if (typeSelect && amountInput) {
            const type = typeSelect.value;
            const amount = parseFloat(amountInput.value) || 0;
            if (type === 'Debit') totalDebit += amount;
            else totalCredit += amount;
        }
    });

    if (DOM.vTotalDebit) DOM.vTotalDebit.textContent = formatPKR(totalDebit);
    if (DOM.vTotalCredit) DOM.vTotalCredit.textContent = formatPKR(totalCredit);

    const diff = Math.abs(totalDebit - totalCredit);
    if (DOM.vBalanceBadge) {
        DOM.vBalanceBadge.className = 'diff-badge balanced';
        DOM.vBalanceBadge.style.background = '#ECFDF5';
        DOM.vBalanceBadge.style.color = '#047857';
        DOM.vBalanceBadge.style.border = '1px solid #A7F3D0';

        if (totalDebit === 0 && totalCredit === 0) {
            DOM.vBalanceBadge.textContent = '✓ Ready';
        } else if (diff < 0.05) {
            DOM.vBalanceBadge.textContent = `✓ Balanced (${formatPKR(totalDebit)})`;
        } else {
            DOM.vBalanceBadge.textContent = `✓ Auto-Balancing (Diff: ${formatPKR(diff)})`;
        }
    }

    if (DOM.vFormDate) { DOM.vFormDate.addEventListener('change', updateVoucherSequenceOnDateChange); }
    const _gpDateEl = document.getElementById('gpFormDate'); if (_gpDateEl) { _gpDateEl.addEventListener('change', updateGatePassSequenceOnDateChange); }
    if (DOM.btnSubmitVoucher) {
        DOM.btnSubmitVoucher.disabled = false;
    }
}

async function handleVoucherSubmit(e) {
    e.preventDefault();

    let totalDebit = 0;
    let totalCredit = 0;
    const entries = [];

    const rows = DOM.voucherLinesBody.querySelectorAll('tr');
    if (rows.length < 2) {
        alert('Double entry requires at least 2 line entries.');
        return;
    }

    for (let tr of rows) {
        const accId = parseInt(tr.querySelector('.v-line-account').value);
        const partyVal = tr.querySelector('.v-line-party').value;
        const partyId = partyVal ? parseInt(partyVal) : null;
        const type = tr.querySelector('.v-line-type').value;
        const amount = parseFloat(tr.querySelector('.v-line-amount').value) || 0;

        if (!accId || amount <= 0) {
            continue; // Skip unfilled row gracefully
        }

        if (type === 'Debit') totalDebit += amount;
        else totalCredit += amount;

        entries.push({
            account_id: accId,
            party_id: partyId,
            entry_type: type,
            amount: amount,
            narration: DOM.vFormNarration.value.trim()
        });
    }

// Difference check removed: system auto-balances seamlessly

    const vNumVal = (DOM.vFormVoucherNumber && DOM.vFormVoucherNumber.value) ? DOM.vFormVoucherNumber.value.trim() : null;
    const payload = {
        voucher_number: vNumVal,
        voucher_type: DOM.vFormType.value,
        date: DOM.vFormDate.value ? new Date(DOM.vFormDate.value).toISOString() : new Date().toISOString(),
        reference_no: DOM.vFormRef.value.trim(),
        narration: DOM.vFormNarration.value.trim(),
        client_uuid: 'v-' + Date.now() + '-' + Math.random().toString(36).substring(2, 7),
        entries: entries
    };

    DOM.btnSubmitVoucher.disabled = true;
    DOM.btnSubmitVoucher.textContent = 'Posting...';

    try {
        const res = await fetch(`${API_BASE}/api/v1/vouchers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to post voucher.');
        }

        const createdVoucher = await res.json();
        DOM.modalVoucher.setAttribute('hidden', '');
        await refreshAllData();
        viewVoucherSlip(createdVoucher.id);
    } catch (err) {
        const isNetworkErr = !navigator.onLine
            || err.name === 'TypeError'
            || (err.message && (
                err.message.toLowerCase().includes('failed to fetch')
                || err.message.toLowerCase().includes('networkerror')
                || err.message.toLowerCase().includes('network request failed')
            ));
        if (isNetworkErr) {
            STATE.offlineQueue.push(payload);
            saveOfflineQueueToStorage();
            DOM.modalVoucher.setAttribute('hidden', '');
            alert('✓ Offline Mode: Voucher saved locally. Will sync when online.');
            updateOfflineStatusUI();
        } else {
            alert('❌ Voucher Error: ' + (err.message || 'Save failed. Please try again.'));
        }
    } finally {
        DOM.btnSubmitVoucher.disabled = false;
        DOM.btnSubmitVoucher.textContent = 'Post Voucher to Ledger';
    }
}

// ---------------------------------------------------------------------------
// VIEW VOUCHER SLIP
// ---------------------------------------------------------------------------
async function viewVoucherSlip(voucherId) {
    STATE.currentSlipVoucherId = voucherId;
    try {
        const res = await fetch(`${API_BASE}/api/v1/vouchers/${voucherId}`);
        if (!res.ok) throw new Error('Voucher details not found');
        const v = await res.json();

        if (STATE.profile) {
            DOM.slipCompanyName.textContent = STATE.profile.company_name || 'Tri Agro Farms';
            DOM.slipCompanyAddress.textContent = `${STATE.profile.address || 'Sheikhupura'} \u2022 Phone: ${STATE.profile.phone || '0320944803'}`;
        }

        DOM.slipVoucherTypeTitle.textContent = v.voucher_type + ' Voucher';
        DOM.slipVoucherNumber.textContent = v.voucher_number;
        STATE.currentSlipVoucherNumber = v.voucher_number;
        DOM.slipReference.textContent = v.reference_no || '-';
        DOM.slipDate.textContent = formatDate(v.date);
        DOM.slipNarration.textContent = v.narration || '-';
        DOM.slipPreparedBy.textContent = v.created_by || 'Muhammad Saad';

        DOM.slipEntriesTableBody.innerHTML = '';
        let totalD = 0;
        let totalC = 0;

        v.entries.forEach(e => {
            const isDebit = e.entry_type === 'Debit';
            if (isDebit) totalD += e.amount;
            else totalC += e.amount;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${e.account_name}</strong></td>
                <td>${e.party_name || '-'}</td>
                <td class="table-amount">${isDebit ? formatPKR(e.amount) : '-'}</td>
                <td class="table-amount">${!isDebit ? formatPKR(e.amount) : '-'}</td>
            `;
            DOM.slipEntriesTableBody.appendChild(tr);
        });

        DOM.slipEntriesTableFoot.innerHTML = `
            <tr>
                <td colspan="2" style="text-align: right;">Total Amount (PKR):</td>
                <td class="table-amount" style="color: #059669;">${formatPKR(totalD)}</td>
                <td class="table-amount" style="color: #2563EB;">${formatPKR(totalC)}</td>
            </tr>
        `;

        DOM.modalVoucherSlip.removeAttribute('hidden');
    } catch (err) {
        alert('Could not view voucher: ' + err.message);
    }
}

// ---------------------------------------------------------------------------
// MODAL: ADD / EDIT PARTY
// ---------------------------------------------------------------------------
function openPartyModal(partyId = null) {
    DOM.partyForm.reset();
    DOM.partyFormId.value = '';

    if (partyId) {
        const party = STATE.parties.find(p => p.id === partyId);
        if (!party) return;
        DOM.partyModalTitle.textContent = `Edit Commercial Party: ${party.name}`;
        DOM.partyFormId.value = party.id;
        DOM.partyFormName.value = party.name;
        DOM.partyFormType.value = party.type;
        DOM.partyFormContact.value = party.contact_person || '';
        DOM.partyFormPhone.value = party.phone || '';
        DOM.partyFormEmail.value = party.email || '';
        DOM.partyFormCity.value = party.city || '';
        DOM.partyFormAddress.value = party.address || '';
        DOM.partyFormCreditLimit.value = party.credit_limit || 0;
        DOM.partyOpeningBalGroup.style.display = 'none'; // Not editable on existing party
    } else {
        DOM.partyModalTitle.textContent = 'Add Commercial Party';
        DOM.partyOpeningBalGroup.style.display = 'block';
    }

    DOM.modalParty.removeAttribute('hidden');
}

async function handlePartySubmit(e) {
    e.preventDefault();
    const partyId = DOM.partyFormId.value;

    const payload = {
        name: DOM.partyFormName.value.trim(),
        type: DOM.partyFormType.value,
        contact_person: DOM.partyFormContact.value.trim(),
        phone: DOM.partyFormPhone.value.trim(),
        email: DOM.partyFormEmail.value.trim(),
        city: DOM.partyFormCity.value.trim(),
        address: DOM.partyFormAddress.value.trim(),
        credit_limit: parseFloat(DOM.partyFormCreditLimit.value) || 0
    };

    try {
        let res;
        if (partyId) {
            // Update existing party
            res = await fetch(`${API_BASE}/api/v1/parties/${partyId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            // Create new party
            payload.current_balance = parseFloat(DOM.partyFormBalance.value) || 0;
            res = await fetch(`${API_BASE}/api/v1/parties`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Party operation failed');
        }

        DOM.modalParty.setAttribute('hidden', '');
        await fetchParties();
        await fetchDashboardSummary();
        alert('Party information saved successfully.');
    } catch (err) {
        alert(err.message);
    }
}

// ---------------------------------------------------------------------------
// MODAL: ADD ACCOUNT
// ---------------------------------------------------------------------------
function openAccountModal(accId = null) {
    DOM.accountForm.reset();
    DOM.accountFormId.value = '';

    if (accId) {
        const acc = STATE.accounts.find(a => a.id === accId);
        if (!acc) return;
        DOM.accountModalTitle.textContent = `Edit Account: ${acc.name}`;
        DOM.accountFormId.value = acc.id;
        DOM.accountFormCode.value = acc.code;
        DOM.accountFormName.value = acc.name;
        DOM.accountFormType.value = acc.type;
        DOM.accountFormDesc.value = acc.description || '';
        if (DOM.accountOpeningBalGroup) DOM.accountOpeningBalGroup.style.display = 'none';
    } else {
        DOM.accountModalTitle.textContent = 'Add General Ledger Account';
        if (DOM.accountOpeningBalGroup) DOM.accountOpeningBalGroup.style.display = 'block';
    }

    DOM.modalAccount.removeAttribute('hidden');
}

async function handleAccountSubmit(e) {
    e.preventDefault();
    const accId = DOM.accountFormId.value;

    const payload = {
        code: DOM.accountFormCode.value.trim(),
        name: DOM.accountFormName.value.trim(),
        type: DOM.accountFormType.value,
        description: DOM.accountFormDesc.value.trim()
    };

    try {
        let res;
        if (accId) {
            res = await fetch(`${API_BASE}/api/v1/accounts/${accId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            payload.balance = parseFloat(DOM.accountFormBalance.value) || 0;
            payload.is_active = true;
            res = await fetch(`${API_BASE}/api/v1/accounts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Account operation failed');
        }

        DOM.modalAccount.setAttribute('hidden', '');
        await fetchAccounts();
        await fetchDashboardSummary();
        alert('Account saved successfully.');
    } catch (err) {
        alert(err.message);
    }
}

// ---------------------------------------------------------------------------
// MODAL: RECORD DAILY EXPENSE
// ---------------------------------------------------------------------------
function openExpenseModal() {
    const modal = DOM.modalExpense || document.getElementById('modalExpense');
    if (!modal) return;
    const form = DOM.formAddExpense || document.getElementById('formAddExpense');
    if (form) form.reset();

    const dateEl = DOM.expFormDate || document.getElementById('expFormDate');
    if (dateEl) {
        dateEl.value = new Date().toISOString().split('T')[0];
    }
    populateExpensePaymentAccounts();

    const refEl = DOM.expFormReference || document.getElementById('expFormReference');
    try {
        fetch(`${API_BASE}/api/v1/vouchers/next-sequence`).then(r => r.json()).then(seq => {
            if (refEl && (!refEl.value || refEl.value.startsWith('TA-ref-'))) {
                refEl.value = seq.next_reference_no || '';
            }
        }).catch(() => {});
    } catch (e) {}

    modal.removeAttribute('hidden');
    const amtEl = DOM.expFormAmount || document.getElementById('expFormAmount');
    if (amtEl) amtEl.focus();
}

function populateExpensePaymentAccounts() {
    const payAccEl = DOM.expFormPaymentAccount || document.getElementById('expFormPaymentAccount');
    if (!payAccEl) return;
    payAccEl.innerHTML = '';
    const assetAccounts = (STATE.accounts || []).filter(a => a.type === 'Asset');
    if (assetAccounts.length === 0) {
        const opt = document.createElement('option');
        opt.value = 'Cash in Hand';
        opt.textContent = 'Cash in Hand';
        payAccEl.appendChild(opt);
    } else {
        assetAccounts.forEach(acc => {
            const opt = document.createElement('option');
            opt.value = acc.name;
            opt.dataset.id = acc.id;
            opt.textContent = `${acc.code} - ${acc.name} (Bal: ${formatPKR(acc.balance)})`;
            payAccEl.appendChild(opt);
        });
    }
}

async function handleExpenseSubmit(e) {
    e.preventDefault();
    const btnSubmit = DOM.btnSubmitExpense || document.getElementById('btnSubmitExpense');
    const dateEl = DOM.expFormDate || document.getElementById('expFormDate');
    const amtEl = DOM.expFormAmount || document.getElementById('expFormAmount');
    const narrEl = DOM.expFormNarration || document.getElementById('expFormNarration');
    const refEl = DOM.expFormReference || document.getElementById('expFormReference');
    const modal = DOM.modalExpense || document.getElementById('modalExpense');

    const dateVal = dateEl ? dateEl.value : '';
    const amountVal = amtEl ? parseFloat(amtEl.value) : 0;
    const narrationVal = narrEl ? narrEl.value.trim() : '';
    const referenceVal = refEl ? refEl.value.trim() : '';

    if (isNaN(amountVal) || amountVal <= 0) {
        alert('Please enter a valid expense amount greater than 0.');
        return;
    }

    const payload = {
        date: dateVal ? new Date(dateVal).toISOString() : new Date().toISOString(),
        amount: amountVal,
        narration: narrationVal,
        reference_no: referenceVal || null
    };

    try {
        if (btnSubmit) btnSubmit.disabled = true;
        const res = await fetch(`${API_BASE}/api/v1/expenses`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Expense recording failed');
        }

        if (modal) modal.setAttribute('hidden', '');
        await refreshAllData();
        const filterDateEl = DOM.expenseFilterDate || document.getElementById('expenseFilterDate');
        await fetchExpenses(filterDateEl && filterDateEl.value ? filterDateEl.value : null);
        alert('✓ Expense recorded successfully and posted to General Ledger!');
    } catch (err) {
        alert('Error recording expense: ' + (err.message || err));
    } finally {
        if (btnSubmit) btnSubmit.disabled = false;
    }
}

async function fetchExpenses(dateFilter = null) {
    try {
        let url = `${API_BASE}/api/v1/expenses`;
        if (dateFilter) {
            url += `?date=${encodeURIComponent(dateFilter)}`;
        }
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();

        // Update summary badges
        if (DOM.stripTodayExpense) DOM.stripTodayExpense.textContent = formatPKR(data.today_pkr);
        if (DOM.stripFilteredExpense) DOM.stripFilteredExpense.textContent = formatPKR(data.filtered_total_pkr);
        if (DOM.stripAllTimeExpense) DOM.stripAllTimeExpense.textContent = formatPKR(data.total_all_time_pkr);
        if (DOM.stripNetReceivedMinusExpense) {
            const rec = (STATE.summary && STATE.summary.amount_received_pkr) || 0;
            const diff = rec - data.total_all_time_pkr;
            DOM.stripNetReceivedMinusExpense.textContent = formatPKR(diff);
            DOM.stripNetReceivedMinusExpense.style.color = diff >= 0 ? '#059669' : '#DC2626';
        }
        if (DOM.kpiTotalExpenses) DOM.kpiTotalExpenses.textContent = formatPKR(data.total_all_time_pkr);
        if (DOM.kpiTodayExpenseSubtitle) DOM.kpiTodayExpenseSubtitle.textContent = `Today's Expense: ${formatPKR(data.today_pkr)}`;

        // Render table
        if (DOM.expenseTableBody) {
            DOM.expenseTableBody.innerHTML = '';
            if (!data.items || data.items.length === 0) {
                DOM.expenseTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No expense vouchers found for this date.</td></tr>';
                return;
            }

            data.items.forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #1E293B;">${item.date ? item.date.substring(0, 10) : ''}</td>
                    <td><span class="badge" style="background: #FEE2E2; color: #DC2626; font-weight: 600;">${item.voucher_number}</span></td>
                    <td style="font-weight: 600;">${item.category}</td>
                    <td>${item.payment_method || 'Cash in Hand'}</td>
                    <td style="color: var(--text-secondary);">${item.narration || ''}</td>
                    <td class="table-amount" style="color: #DC2626; font-weight: 700;">${formatPKR(item.amount)}</td>
                    <td style="text-align: center; white-space: nowrap;">
                        <button type="button" class="btn btn-secondary btn-sm" onclick="viewVoucherSlip(${item.voucher_id})" title="View Slip">Slip</button>
                        <button type="button" class="btn btn-sm" onclick="deleteExpenseItem(${item.voucher_id}, '${item.voucher_number}')" title="Delete Expense" style="margin-left: 4px; background: #EF4444; color: #fff; border: 1px solid #DC2626; padding: 4px 8px; border-radius: 4px; cursor: pointer;">Delete</button>
                    </td>
                `;
                DOM.expenseTableBody.appendChild(tr);
            });
        }
    } catch (err) {
        console.warn('fetchExpenses error:', err);
    }
}

// Global exposure for inline onclick handlers
window.viewVoucherSlip = viewVoucherSlip;
window.inspectAccountGl = inspectAccountGl;
window.openPartyModal = openPartyModal;
window.inspectPartyStatement = inspectPartyStatement;
window.openExpenseModal = openExpenseModal;


// ---------------------------------------------------------------------------
// DYNAMIC REFRESH OF VOUCHER LINE DROPDOWNS
// ---------------------------------------------------------------------------
function refreshVoucherLineDropdowns() {
    if (!DOM.voucherLinesBody) return;
    const rows = DOM.voucherLinesBody.querySelectorAll('tr');
    rows.forEach(tr => {
        const accSelect = tr.querySelector('.v-line-account');
        const partySelect = tr.querySelector('.v-line-party');
        if (accSelect) {
            const curr = accSelect.value;
            let accOptions = '<option value="">-- Choose Account --</option>';
            STATE.accounts.forEach(a => {
                accOptions += `<option value="${a.id}">${a.code} - ${a.name}</option>`;
            });
            accOptions += '<option value="__ADD_NEW_ACC__" style="color: #059669; font-weight: 700;">+ Add New Account...</option>';
            accSelect.innerHTML = accOptions;
            if (curr && curr !== '__ADD_NEW_ACC__') accSelect.value = curr;
        }
        if (partySelect) {
            const curr = partySelect.value;
            let partyOptions = '<option value="">-- None (General) --</option>';
            STATE.parties.forEach(p => {
                partyOptions += `<option value="${p.id}">${p.name} (${p.type})</option>`;
            });
            partyOptions += '<option value="__ADD_NEW_PARTY__" style="color: #2563EB; font-weight: 700;">+ Add New Party / Customer...</option>';
            partySelect.innerHTML = partyOptions;
            if (curr && curr !== '__ADD_NEW_PARTY__') partySelect.value = curr;
        }
    });
}

// ---------------------------------------------------------------------------
// DELETE ACCOUNT
// ---------------------------------------------------------------------------
async function deleteAccount(accId, accName) {
    if (!confirm(`Are you sure you want to delete Account "${accName}"?\n\nThis will remove it from the Chart of Accounts and dropdowns.`)) {
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/v1/accounts/${accId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to delete account');
        }
        await fetchAccounts();
        renderAccountsTable();
        refreshVoucherLineDropdowns();
        alert(`Account "${accName}" deleted successfully.`);
    } catch (err) {
        alert(err.message);
    }
}

// ---------------------------------------------------------------------------
// DELETE PARTY
// ---------------------------------------------------------------------------
async function deleteParty(partyId, partyName) {
    if (!confirm(`Are you sure you want to delete Party "${partyName}"?\n\nThis will remove them from the Directory and dropdowns.`)) {
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/v1/parties/${partyId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to delete party');
        }
        await fetchParties();
        renderPartiesTable();
        refreshVoucherLineDropdowns();
        alert(`Party "${partyName}" deleted successfully.`);
    } catch (err) {
        alert(err.message);
    }
}

window.deleteAccount = deleteAccount;
window.deleteParty = deleteParty;
window.refreshVoucherLineDropdowns = refreshVoucherLineDropdowns;


// ---------------------------------------------------------------------------
// DELETE VOUCHER
// ---------------------------------------------------------------------------
async function deleteVoucher(voucherId, voucherNumber) {
    const vName = voucherNumber || `Voucher #${voucherId}`;
    if (!confirm(`Are you sure you want to delete ${vName}?\n\nThis will permanently delete this transaction and reverse all account and party balances.`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/v1/vouchers/${voucherId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to delete voucher');
        }

        // Close slip modal if it was open
        if (DOM.modalVoucherSlip && !DOM.modalVoucherSlip.hasAttribute('hidden')) {
            DOM.modalVoucherSlip.setAttribute('hidden', '');
        }

        alert(`${vName} has been successfully deleted and ledger balances reversed.`);
        await refreshAllData();
    } catch (err) {
        alert('Error deleting voucher: ' + err.message);
    }
}

window.deleteVoucher = deleteVoucher;


// ===========================================================================
// INCOME, EXPENSES, PAYMENTS & UNIFIED LEDGER MODULE
// ===========================================================================

// --- Income State & Functions ---
let incomeCurrentFilter = { itype: 'all', date: '', search: '' };

async function fetchIncomes() {
    const tbody = document.getElementById('incomeTableBody');
    if (!tbody) return;

    let url = `${API_BASE}/api/v1/income?`;
    if (incomeCurrentFilter.date) url += `date=${encodeURIComponent(incomeCurrentFilter.date)}&`;
    if (incomeCurrentFilter.search) url += `search=${encodeURIComponent(incomeCurrentFilter.search)}&`;
    if (incomeCurrentFilter.itype === 'receipt') url += `is_receipt=true&`;
    if (incomeCurrentFilter.itype === 'revenue') url += `is_receipt=false&`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to load income records');
        const data = await res.json();
        STATE.incomes = data.items || [];

        // Update KPIs
        const kpiRev = document.getElementById('kpiIncomeTotalRevenue');
        const kpiRcp = document.getElementById('kpiIncomeTotalReceipts');
        const kpiToday = document.getElementById('kpiIncomeToday');
        if (kpiRev) kpiRev.textContent = formatPKR(data.total_income_pkr || 0);
        if (kpiRcp) kpiRcp.textContent = formatPKR(data.total_receipts_pkr || 0);
        if (kpiToday) kpiToday.textContent = formatPKR(data.today_pkr || 0);

        // Update Summary Strip & Table Footer
        const stripCount = document.getElementById('stripIncomeCount');
        const stripTotal = document.getElementById('stripFilteredIncome');
        const stripRev = document.getElementById('stripDirectRevenue');
        const stripRcp = document.getElementById('stripCustomerReceipts');
        const footTotal = document.getElementById('incomeFootTotal');

        const activeItems = (data.items || []).filter(i => !i.is_voided);
        const filteredSum = data.filtered_total_pkr !== undefined ? data.filtered_total_pkr : activeItems.reduce((acc, x) => acc + (x.amount || 0), 0);
        const directSum = activeItems.filter(i => !i.is_customer_receipt).reduce((acc, x) => acc + (x.amount || 0), 0);
        const receiptSum = activeItems.filter(i => i.is_customer_receipt).reduce((acc, x) => acc + (x.amount || 0), 0);

        if (stripCount) stripCount.textContent = `${(data.items || []).length} entries`;
        if (stripTotal) stripTotal.textContent = formatPKR(filteredSum);
        if (stripRev) stripRev.textContent = formatPKR(directSum);
        if (stripRcp) stripRcp.textContent = formatPKR(receiptSum);
        if (footTotal) footTotal.textContent = formatPKR(filteredSum);

        renderIncomeTable(STATE.incomes);
    } catch (err) {
        console.error('Error fetching income:', err);
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--error-red); padding: 1.5rem;">Error loading income: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderIncomeTable(items) {
    const tbody = document.getElementById('incomeTableBody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2rem; color: var(--text-muted);">No income transactions found for selected filters.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => {
        const isVoid = item.is_voided;
        const typeBadge = item.is_customer_receipt
            ? `<span class="badge" style="background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE;">Receipt</span>`
            : `<span class="badge badge-cr">Revenue</span>`;
        const statusBadge = isVoid
            ? `<span class="badge badge-dr" style="margin-left: 4px;" title="${escapeHtml(item.void_reason || 'Voided')}">Voided</span>`
            : `<span class="badge" style="background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; margin-left: 4px;">Active</span>`;

        const rowStyle = isVoid ? 'opacity: 0.55; text-decoration: line-through;' : '';

        return `
            <tr style="${rowStyle}">
                <td>${formatDate(item.date)}</td>
                <td style="font-weight: 600; font-family: monospace;">${escapeHtml(item.transaction_number)}</td>
                <td><strong>${escapeHtml(item.income_category)}</strong></td>
                <td>${escapeHtml(item.party_name || 'Walk-in / Cash')}</td>
                <td><span class="badge" style="background: #F1F5F9; color: var(--text-secondary);">${escapeHtml(item.payment_method)}</span></td>
                <td style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(item.reference_no || '-')}</td>
                <td style="max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(item.description || '')}">${escapeHtml(item.description || '-')}</td>
                <td style="text-align: right; font-weight: 700; color: #059669;">${formatPKR(item.amount)}</td>
                <td style="text-align: center;"><div style="display: inline-flex; gap: 5px; align-items: center; justify-content: center;">${typeBadge}${statusBadge}</div></td>
                <td style="text-align: center; white-space: nowrap;">
                    ${item.voucher_id ? `<button type="button" class="btn btn-secondary btn-sm" onclick="viewVoucherSlip(${item.voucher_id})" style="padding: 0.25rem 0.55rem; font-size: 0.78rem; font-weight: 700; background: #ECFDF5; color: #065F46; border: 1.5px solid #059669;" title="View Voucher Slip">👁️ Slip</button>` : ''}
                    <button type="button" class="btn btn-secondary btn-sm" onclick="openEditIncomeModal(${item.id})" style="padding: 0.25rem 0.55rem; font-size: 0.78rem; font-weight: 700; background: #F1F5F9; color: var(--text-primary); border: 1px solid #CBD5E1; margin-left: 4px;" title="Edit Income Record">✏️ Edit</button>
                    <button type="button" class="btn btn-sm" onclick="deleteIncomeTransaction(${item.id}, '${escapeHtml(item.transaction_number)}')" style="padding: 0.25rem 0.55rem; font-size: 0.78rem; background: #EF4444; color: #fff; border: 1px solid #DC2626; border-radius: 4px; margin-left: 4px; cursor: pointer; font-weight: 700;" title="Delete Income Record">&times; Delete</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function openIncomeModal() {
    const modal = document.getElementById('modalIncome');
    if (!modal) return;

    const dateInput = document.getElementById('incFormDate');
    const amountInput = document.getElementById('incFormAmount');
    const catInput = document.getElementById('incFormCategory');
    const custSelect = document.getElementById('incFormCustomer');
    const descInput = document.getElementById('incFormDescription');
    const refInput = document.getElementById('incFormReference');
    const notesInput = document.getElementById('incFormNotes');
    const radioRev = document.getElementById('incRadioRevenue');
    const radioRcp = document.getElementById('incRadioReceipt');
    const lblRcp = document.getElementById('lblIncRadioReceipt');
    const helpRcp = document.getElementById('incReceiptHelpText');
    const legacyCheck = document.getElementById('incFormIsReceipt');

    const today = new Date().toISOString().split('T')[0];
    if (dateInput) dateInput.value = today;
    if (amountInput) amountInput.value = '';
    if (catInput) catInput.value = 'Farm Produce Sales';
    if (descInput) descInput.value = '';
    if (notesInput) notesInput.value = '';

    function syncRadioState() {
        const hasCustomer = !!(custSelect && custSelect.value);
        if (radioRcp) radioRcp.disabled = !hasCustomer;
        if (lblRcp) lblRcp.style.opacity = hasCustomer ? '1' : '0.5';
        if (helpRcp) {
            helpRcp.textContent = hasCustomer
                ? 'Settles receivable for ' + (custSelect.options[custSelect.selectedIndex]?.text || 'selected customer')
                : 'Requires selecting a customer above. Settles customer receivable without duplicating revenue.';
        }
        if (!hasCustomer && radioRev) {
            radioRev.checked = true;
        }
        if (legacyCheck) {
            legacyCheck.checked = (radioRcp && radioRcp.checked && hasCustomer) ? true : false;
        }
    }

    if (custSelect) {
        custSelect.innerHTML = `<option value="">-- Walk-in / Cash (No Registered Customer) --</option>` +
            STATE.parties
                .filter(p => p.type === 'Customer')
                .map(p => `<option value="${p.id}">${escapeHtml(p.name)} (${p.city || 'Karachi'}) - Bal: ${formatPKR(p.current_balance || p.opening_balance || 0)}</option>`)
                .join('');

        custSelect.onchange = syncRadioState;
    }

    if (radioRev) {
        radioRev.checked = true;
        radioRev.onchange = () => { if (legacyCheck) legacyCheck.checked = false; };
    }
    if (radioRcp) {
        radioRcp.onchange = () => { if (legacyCheck) legacyCheck.checked = radioRcp.checked; };
    }
    syncRadioState();

    if (refInput) {
        try {
            const res = await fetch(`${API_BASE}/api/v1/income/next-number`);
            if (res.ok) {
                const seq = await res.json();
                refInput.value = seq.next_reference_no || '';
            }
        } catch (e) {
            refInput.value = '';
        }
    }

    modal.removeAttribute('hidden');
    if (amountInput) amountInput.focus();
}

async function handleIncomeSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSubmitIncome');
    if (btn) btn.disabled = true;

    try {
        const dateInput = document.getElementById('incFormDate');
        const amountInput = document.getElementById('incFormAmount');
        const catInput = document.getElementById('incFormCategory');
        const methodSelect = document.getElementById('incFormMethod');
        const custSelect = document.getElementById('incFormCustomer');
        const descInput = document.getElementById('incFormDescription');
        const refInput = document.getElementById('incFormReference');
        const notesInput = document.getElementById('incFormNotes');
        const radioRcp = document.getElementById('incRadioReceipt');
        const legacyCheck = document.getElementById('incFormIsReceipt');

        const dateVal = dateInput ? dateInput.value : '';
        const amountVal = amountInput ? parseFloat(amountInput.value) : 0;
        const catVal = catInput ? catInput.value.trim() : 'General Income';
        const methodVal = methodSelect ? methodSelect.value : 'Cash in Hand';
        const custVal = custSelect ? custSelect.value : '';
        const descVal = descInput ? descInput.value.trim() : '';
        const refVal = refInput ? refInput.value.trim() : '';
        const notesVal = notesInput ? notesInput.value.trim() : '';

        // Safe evaluation of receipt classification
        const isRcp = !!(
            ((radioRcp && radioRcp.checked) || (legacyCheck && legacyCheck.checked)) &&
            custVal
        );

        if (isNaN(amountVal) || amountVal <= 0) {
            throw new Error('Please enter a valid amount greater than 0.');
        }

        const payload = {
            date: dateVal ? new Date(dateVal).toISOString() : new Date().toISOString(),
            income_category: catVal || 'General Income',
            party_id: custVal ? parseInt(custVal) : null,
            amount: amountVal,
            payment_method: methodVal,
            reference_no: refVal || null,
            description: descVal,
            notes: notesVal || null,
            is_customer_receipt: isRcp
        };

        const res = await fetch(`${API_BASE}/api/v1/income`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to record income');
        }

        const created = await res.json();
        alert(`Income transaction ${created.transaction_number} posted successfully!`);

        const modal = document.getElementById('modalIncome');
        if (modal) modal.setAttribute('hidden', '');

        await fetchIncomes();
        await refreshAllData();
    } catch (err) {
        alert(err.message || 'Error recording income');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function openEditIncomeModal(incomeId) {
    const item = (STATE.incomes || []).find(i => i.id === incomeId);
    if (!item) {
        alert('Transaction not found');
        return;
    }
    const modal = document.getElementById('modalEditIncome');
    if (!modal) return;

    document.getElementById('editIncId').value = item.id;
    const sub = document.getElementById('editIncHeaderSub');
    if (sub) sub.textContent = `Transaction ${item.transaction_number}`;

    const dateInput = document.getElementById('editIncDate');
    if (dateInput) {
        dateInput.value = item.date ? item.date.split('T')[0] : '';
    }
    const amountInput = document.getElementById('editIncAmount');
    if (amountInput) amountInput.value = item.amount || '';

    const catInput = document.getElementById('editIncCategory');
    if (catInput) catInput.value = item.income_category || 'Farm Produce Sales';

    const methodSelect = document.getElementById('editIncMethod');
    if (methodSelect) methodSelect.value = item.payment_method || 'Cash in Hand';

    const custSelect = document.getElementById('editIncCustomer');
    if (custSelect) {
        custSelect.innerHTML = `<option value="">-- Walk-in / Cash (No Registered Customer) --</option>` +
            STATE.parties
                .filter(p => p.type === 'Customer')
                .map(p => `<option value="${p.id}" ${p.id === item.party_id ? 'selected' : ''}>${escapeHtml(p.name)} (${p.city || 'Karachi'})</option>`)
                .join('');
    }

    const radioRev = document.getElementById('editIncRadioRevenue');
    const radioRcp = document.getElementById('editIncRadioReceipt');
    if (item.is_customer_receipt && item.party_id && radioRcp) {
        radioRcp.checked = true;
    } else if (radioRev) {
        radioRev.checked = true;
    }

    const descInput = document.getElementById('editIncDescription');
    if (descInput) descInput.value = item.description || '';

    const refInput = document.getElementById('editIncReference');
    if (refInput) refInput.value = item.reference_no || '';

    const notesInput = document.getElementById('editIncNotes');
    if (notesInput) notesInput.value = item.notes || '';

    modal.removeAttribute('hidden');
}

async function handleEditIncomeSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSubmitEditIncome');
    if (btn) btn.disabled = true;

    try {
        const id = document.getElementById('editIncId').value;
        const dateVal = document.getElementById('editIncDate').value;
        const amountVal = parseFloat(document.getElementById('editIncAmount').value);
        const catVal = document.getElementById('editIncCategory').value.trim();
        const methodVal = document.getElementById('editIncMethod').value;
        const custVal = document.getElementById('editIncCustomer').value;
        const radioRcp = document.getElementById('editIncRadioReceipt');
        const isRcp = (radioRcp && radioRcp.checked && !!custVal);
        const descVal = document.getElementById('editIncDescription').value.trim();
        const refVal = document.getElementById('editIncReference').value.trim();
        const notesVal = document.getElementById('editIncNotes').value.trim();

        if (isNaN(amountVal) || amountVal <= 0) {
            throw new Error('Please enter a valid amount greater than 0.');
        }

        const payload = {
            date: dateVal ? new Date(dateVal).toISOString() : undefined,
            income_category: catVal || 'General Income',
            party_id: custVal ? parseInt(custVal) : null,
            amount: amountVal,
            payment_method: methodVal,
            reference_no: refVal || null,
            description: descVal,
            notes: notesVal || null,
            is_customer_receipt: isRcp
        };

        const res = await fetch(`${API_BASE}/api/v1/income/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to update income transaction');
        }

        alert('Income transaction updated and ledger adjusted successfully!');
        const modal = document.getElementById('modalEditIncome');
        if (modal) modal.setAttribute('hidden', '');

        await fetchIncomes();
        await refreshAllData();
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function voidIncomeTransaction(id, trxNum) {
    const reason = prompt(`Enter reason to VOID transaction ${trxNum}:\n\nThis will reverse the financial ledger entries.`);
    if (!reason || !reason.trim()) return;

    try {
        const res = await fetch(`${API_BASE}/api/v1/income/${id}/void?reason=${encodeURIComponent(reason.trim())}`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to void income transaction');
        }
        alert(`Transaction ${trxNum} voided and reversed successfully.`);
        await fetchIncomes();
        await refreshAllData();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

window.openIncomeModal = openIncomeModal;
window.openEditIncomeModal = openEditIncomeModal;
window.voidIncomeTransaction = voidIncomeTransaction;


// --- Payments & Receipts State & Functions ---
let paymentCurrentFilter = { ptype: '', date: '', search: '' };

async function fetchPayments() {
    const tbody = document.getElementById('paymentsTableBody');
    if (!tbody) return;

    let url = `${API_BASE}/api/v1/payments?`;
    if (paymentCurrentFilter.ptype) url += `payment_type=${encodeURIComponent(paymentCurrentFilter.ptype)}&`;
    if (paymentCurrentFilter.date) url += `date=${encodeURIComponent(paymentCurrentFilter.date)}&`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to load payments');
        const data = await res.json();
        STATE.payments = data.items || [];

        // Apply client text search if needed
        let list = STATE.payments;
        if (paymentCurrentFilter.search) {
            const s = paymentCurrentFilter.search.toLowerCase();
            list = list.filter(p =>
                (p.payment_number || '').toLowerCase().includes(s) ||
                (p.party_name || '').toLowerCase().includes(s) ||
                (p.reference_no || '').toLowerCase().includes(s) ||
                (p.notes || '').toLowerCase().includes(s)
            );
        }

        // Update KPIs
        const kpiRcp = document.getElementById('kpiPaymentTotalReceipts');
        const kpiSup = document.getElementById('kpiPaymentTotalSupplier');
        const kpiNet = document.getElementById('kpiPaymentNetMovement');
        if (kpiRcp) kpiRcp.textContent = formatPKR(data.total_receipts_pkr || 0);
        if (kpiSup) kpiSup.textContent = formatPKR(data.total_supplier_payments_pkr || 0);
        if (kpiNet) {
            const net = (data.total_receipts_pkr || 0) - (data.total_supplier_payments_pkr || 0);
            kpiNet.textContent = formatPKR(net);
            kpiNet.style.color = net >= 0 ? '#059669' : '#DC2626';
        }

        renderPaymentsTable(list);
    } catch (err) {
        console.error('Error fetching payments:', err);
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--error-red); padding: 1.5rem;">Error loading payments: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderPaymentsTable(items) {
    const tbody = document.getElementById('paymentsTableBody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2rem; color: var(--text-muted);">No payment records found for selected filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(p => {
        const isReceipt = (p.payment_type || '').toLowerCase().includes('receipt');
        const typeBadge = isReceipt
            ? `<span class="badge" style="background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;">Customer Receipt</span>`
            : `<span class="badge" style="background: #FEF2F2; color: #DC2626; border: 1px solid #FCA5A5;">Supplier Payment</span>`;

        const isVoid = p.is_voided;
        const statusBadge = isVoid
            ? `<span class="badge badge-dr" style="margin-left: 4px;" title="${escapeHtml(p.void_reason || 'Voided')}">Voided</span>`
            : '';

        const amtColor = isReceipt ? '#059669' : '#DC2626';
        const sign = isReceipt ? '+' : '&minus;';
        const rowStyle = isVoid ? 'opacity: 0.55; text-decoration: line-through;' : '';

        return `
            <tr style="${rowStyle}">
                <td style="font-weight: 600; font-family: monospace;">${escapeHtml(p.payment_number)}</td>
                <td>${formatDate(p.payment_date)}</td>
                <td>${typeBadge}${statusBadge}</td>
                <td><strong>${escapeHtml(p.party_name || 'N/A')}</strong></td>
                <td><span class="badge" style="background: #F1F5F9; color: var(--text-secondary);">${escapeHtml(p.payment_method)}</span></td>
                <td style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(p.reference_no || '-')}</td>
                <td style="max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(p.notes || '')}">${escapeHtml(p.notes || '-')}</td>
                <td style="text-align: right; font-weight: 700; color: ${amtColor};">${sign} ${formatPKR(p.amount)}</td>
                <td style="text-align: right; font-weight: 600; font-size: 0.85rem; color: var(--text-secondary);">${formatPKR(p.remaining_balance_pkr || 0)}</td>
                <td style="text-align: center; white-space: nowrap;">
                    ${p.voucher_id ? `<button type="button" class="btn btn-secondary btn-sm" onclick="viewVoucherSlip(${p.voucher_id})" style="padding: 0.25rem 0.6rem; font-size: 0.78rem; font-weight: 700; background: #ECFDF5; color: #065F46; border: 1.5px solid #059669;" title="View Slip">👁️ View Slip</button>` : ''}
                    <button type="button" class="btn btn-sm" onclick="deletePaymentTransaction(${p.id}, '${escapeHtml(p.payment_number || 'Payment')}')" style="padding: 0.25rem 0.6rem; font-size: 0.78rem; background: #EF4444; color: #fff; border: 1px solid #DC2626; border-radius: 4px; margin-left: 6px; cursor: pointer; font-weight: 700;" title="Delete Payment Record">&times; Delete</button>
                </td>
            </tr>
        `;
    }).join('');
}

function updatePaymentPartyDropdown() {
    const typeSelect = document.getElementById('payFormType');
    const partySelect = document.getElementById('payFormParty');
    const label = document.getElementById('payFormPartyLabel');
    if (!typeSelect || !partySelect) return;

    const isReceipt = typeSelect.value === 'CustomerReceipt';
    if (label) label.textContent = isReceipt ? 'Customer (Debtor) *' : 'Supplier / Vendor (Creditor) *';

    const targetType = isReceipt ? 'Customer' : 'Supplier';
    const parties = STATE.parties.filter(p => {
        if (isReceipt) return p.type === 'Customer';
        return p.type === 'Supplier' || p.type === 'Vendor';
    });

    partySelect.innerHTML = `<option value="">-- Select ${isReceipt ? 'Customer' : 'Supplier'} --</option>` +
        parties.map(p => {
            const bal = p.current_balance || p.opening_balance || 0;
            return `<option value="${p.id}" data-balance="${bal}">${escapeHtml(p.name)} - Current Bal: ${formatPKR(bal)}</option>`;
        }).join('');

    updatePaymentBalanceCalculations();
}

function updatePaymentBalanceCalculations() {
    const partySelect = document.getElementById('payFormParty');
    const amtInput = document.getElementById('payFormAmount');
    const strip = document.getElementById('payPartyBalanceStrip');
    const curBalText = document.getElementById('payCurrentBalanceText');
    const remBalText = document.getElementById('payRemainingBalanceText');

    if (!partySelect || !strip) return;

    const opt = partySelect.selectedOptions[0];
    if (!opt || !opt.value) {
        strip.style.display = 'none';
        return;
    }

    const curBal = parseFloat(opt.getAttribute('data-balance') || 0);
    const enteredAmt = parseFloat(amtInput && amtInput.value ? amtInput.value : 0) || 0;
    const remBal = Math.max(0, curBal - enteredAmt);

    strip.style.display = 'block';
    if (curBalText) curBalText.textContent = formatPKR(curBal);
    if (remBalText) remBalText.textContent = formatPKR(remBal);
}

async function openPaymentModal(defaultType = 'CustomerReceipt') {
    const modal = document.getElementById('modalPayment');
    if (!modal) return;

    const typeSelect = document.getElementById('payFormType');
    const dateInput = document.getElementById('payFormDate');
    const amtInput = document.getElementById('payFormAmount');
    const refInput = document.getElementById('payFormReference');
    const notesInput = document.getElementById('payFormNotes');

    if (typeSelect) typeSelect.value = defaultType;
    const today = new Date().toISOString().split('T')[0];
    if (dateInput) dateInput.value = today;
    if (amtInput) amtInput.value = '';
    if (refInput) refInput.value = '';
    if (notesInput) notesInput.value = '';

    updatePaymentPartyDropdown();

    // Auto-fetch next sequence
    if (refInput) {
        try {
            const res = await fetch(`${API_BASE}/api/v1/payments/next-number?payment_type=${defaultType}`);
            if (res.ok) {
                const seq = await res.json();
                refInput.value = seq.next_reference_no || '';
            }
        } catch (e) {
            refInput.value = '';
        }
    }

    modal.removeAttribute('hidden');
}

async function handlePaymentSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSubmitPayment');
    if (btn) btn.disabled = true;

    try {
        const typeVal = document.getElementById('payFormType').value;
        const partyVal = parseInt(document.getElementById('payFormParty').value);
        const dateVal = document.getElementById('payFormDate').value;
        const amtVal = parseFloat(document.getElementById('payFormAmount').value);
        const methodVal = document.getElementById('payFormMethod').value;
        const refVal = document.getElementById('payFormReference').value.trim();
        const notesVal = document.getElementById('payFormNotes').value.trim();

        if (isNaN(amtVal) || amtVal <= 0) {
            throw new Error('Please enter a valid amount greater than 0.');
        }
        if (!partyVal) {
            throw new Error('Please select a commercial party.');
        }

        const payload = {
            payment_type: typeVal,
            party_id: partyVal,
            payment_date: dateVal ? new Date(dateVal).toISOString() : new Date().toISOString(),
            amount: amtVal,
            payment_method: methodVal,
            reference_no: refVal || null,
            notes: notesVal || null
        };

        const res = await fetch(`${API_BASE}/api/v1/payments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to record payment');
        }

        const created = await res.json();
        alert(`Payment transaction ${created.payment_number} posted successfully!`);

        const modal = document.getElementById('modalPayment');
        if (modal) modal.setAttribute('hidden', '');

        await fetchPayments();
        await refreshAllData();
    } catch (err) {
        alert(err.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function voidPaymentTransaction(id, payNum) {
    const reason = prompt(`Enter reason to VOID payment ${payNum}:\n\nThis will reverse party balances and cancel the financial voucher.`);
    if (!reason || !reason.trim()) return;

    try {
        const res = await fetch(`${API_BASE}/api/v1/payments/${id}/void?reason=${encodeURIComponent(reason.trim())}`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to void payment');
        }
        alert(`Payment ${payNum} voided and reversed successfully.`);
        await fetchPayments();
        await refreshAllData();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

window.openPaymentModal = openPaymentModal;
window.voidPaymentTransaction = voidPaymentTransaction;


// --- Unified Ledger State & Functions ---
let ledgerCurrentFilter = { type: '', fromDate: '', toDate: '', search: '' };

async function fetchUnifiedLedger() {
    const tbody = document.getElementById('ledgerTableBody');
    if (!tbody) return;

    let url = `${API_BASE}/api/v1/ledger?`;
    if (ledgerCurrentFilter.type) url += `transaction_type=${encodeURIComponent(ledgerCurrentFilter.type)}&`;
    if (ledgerCurrentFilter.fromDate) url += `from_date=${encodeURIComponent(ledgerCurrentFilter.fromDate)}&`;
    if (ledgerCurrentFilter.toDate) url += `to_date=${encodeURIComponent(ledgerCurrentFilter.toDate)}&`;
    if (ledgerCurrentFilter.search) url += `search=${encodeURIComponent(ledgerCurrentFilter.search)}&`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to load unified ledger');
        const data = await res.json();
        STATE.ledger = data.items || [];

        // Update KPI Strip
        const stripDr = document.getElementById('ledgerStripDebit');
        const stripCr = document.getElementById('ledgerStripCredit');
        const stripNet = document.getElementById('ledgerStripNet');
        const stripCount = document.getElementById('ledgerStripCount');
        if (stripDr) stripDr.textContent = formatPKR(data.total_debit_pkr || 0);
        if (stripCr) stripCr.textContent = formatPKR(data.total_credit_pkr || 0);
        if (stripNet) {
            stripNet.textContent = formatPKR(data.net_pkr || 0);
            stripNet.style.color = (data.net_pkr || 0) >= 0 ? '#059669' : '#DC2626';
        }
        if (stripCount) stripCount.textContent = (data.total_records || 0).toLocaleString();

        renderLedgerTable(STATE.ledger);
    } catch (err) {
        console.error('Error fetching ledger:', err);
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--error-red); padding: 2rem;">Error loading ledger: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderLedgerTable(items) {
    const tbody = document.getElementById('ledgerTableBody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No double-entry journal records found matching criteria.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(row => {
        const drText = row.debit_pkr > 0 ? formatPKR(row.debit_pkr) : '-';
        const crText = row.credit_pkr > 0 ? formatPKR(row.credit_pkr) : '-';
        const balColor = (row.running_balance_pkr || 0) >= 0 ? '#059669' : '#DC2626';

        let badgeStyle = 'background: #F1F5F9; color: var(--text-secondary);';
        const tt = (row.transaction_type || '').toLowerCase();
        if (tt.includes('income') || tt.includes('sales')) badgeStyle = 'background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;';
        else if (tt.includes('expense') || tt.includes('purchase')) badgeStyle = 'background: #FEF2F2; color: #DC2626; border: 1px solid #FCA5A5;';
        else if (tt.includes('receipt')) badgeStyle = 'background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE;';
        else if (tt.includes('payment')) badgeStyle = 'background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A;';

        return `
            <tr>
                <td>${formatDate(row.transaction_date)}</td>
                <td style="font-weight: 600; font-family: monospace;">
                    <a href="javascript:void(0)" onclick="viewVoucherSlip(${row.voucher_id})" style="color: var(--navy-800); text-decoration: underline;" title="View double-entry slip">
                        ${escapeHtml(row.transaction_number)}
                    </a>
                </td>
                <td><span class="badge" style="${badgeStyle}">${escapeHtml(row.transaction_type)}</span></td>
                <td><strong>${escapeHtml(row.account_name || 'N/A')}</strong></td>
                <td>${escapeHtml(row.party_name || '-')}</td>
                <td style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(row.reference_no || '-')}</td>
                <td style="max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(row.description || '')}">${escapeHtml(row.description || '-')}</td>
                <td style="text-align: right; font-weight: 600; color: #059669;">${drText}</td>
                <td style="text-align: right; font-weight: 600; color: #DC2626;">${crText}</td>
                <td style="text-align: right; font-weight: 700; color: ${balColor};">${formatPKR(row.running_balance_pkr || 0)}</td>
            </tr>
        `;
    }).join('');
}

window.fetchUnifiedLedger = fetchUnifiedLedger;


// --- Wire Event Listeners for Income, Payments & Ledger on Startup ---
function initTransactionsAndLedgerEvents() {
    // Income buttons & filters
    const btnInc = document.getElementById('btnOpenIncomeModal');
    if (btnInc) btnInc.addEventListener('click', openIncomeModal);
    const btnIncTop = document.getElementById('btnOpenIncomeModalTop');
    if (btnIncTop) btnIncTop.addEventListener('click', openIncomeModal);

    const formInc = document.getElementById('formAddIncome');
    if (formInc) formInc.addEventListener('submit', handleIncomeSubmit);
    const formEditInc = document.getElementById('formEditIncome');
    if (formEditInc) formEditInc.addEventListener('submit', handleEditIncomeSubmit);

    const incTabs = document.getElementById('incomeTypeTabs');
    if (incTabs) {
        incTabs.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                incTabs.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                incomeCurrentFilter.itype = tab.getAttribute('data-itype') || 'all';
                fetchIncomes();
            });
        });
    }

    const incDate = document.getElementById('incomeFilterDate');
    if (incDate) {
        incDate.addEventListener('change', () => {
            incomeCurrentFilter.date = incDate.value;
            fetchIncomes();
        });
    }
    const btnIncToday = document.getElementById('btnIncomeFilterToday');
    if (btnIncToday) {
        btnIncToday.addEventListener('click', () => {
            const today = new Date().toISOString().split('T')[0];
            if (incDate) incDate.value = today;
            incomeCurrentFilter.date = today;
            fetchIncomes();
        });
    }
    const btnIncAll = document.getElementById('btnIncomeFilterAll');
    if (btnIncAll) {
        btnIncAll.addEventListener('click', () => {
            if (incDate) incDate.value = '';
            incomeCurrentFilter.date = '';
            fetchIncomes();
        });
    }
    const incSearch = document.getElementById('incomeSearchInput');
    if (incSearch) {
        let timer;
        incSearch.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                incomeCurrentFilter.search = incSearch.value.trim();
                fetchIncomes();
            }, 300);
        });
    }

    // Payments buttons & filters
    const btnPay = document.getElementById('btnOpenPaymentModal');
    if (btnPay) btnPay.addEventListener('click', () => openPaymentModal('CustomerReceipt'));
    const btnPayTop = document.getElementById('btnOpenPaymentModalTop');
    if (btnPayTop) btnPayTop.addEventListener('click', () => openPaymentModal('CustomerReceipt'));

    const formPay = document.getElementById('formAddPayment');
    if (formPay) formPay.addEventListener('submit', handlePaymentSubmit);

    const payTypeSelect = document.getElementById('payFormType');
    if (payTypeSelect) {
        payTypeSelect.addEventListener('change', () => {
            updatePaymentPartyDropdown();
        });
    }
    const payPartySelect = document.getElementById('payFormParty');
    if (payPartySelect) {
        payPartySelect.addEventListener('change', updatePaymentBalanceCalculations);
    }
    const payAmtInput = document.getElementById('payFormAmount');
    if (payAmtInput) {
        payAmtInput.addEventListener('input', updatePaymentBalanceCalculations);
    }

    const payTabs = document.getElementById('paymentTypeTabs');
    if (payTabs) {
        payTabs.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                payTabs.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                paymentCurrentFilter.ptype = tab.getAttribute('data-ptype') || '';
                fetchPayments();
            });
        });
    }
    const payDate = document.getElementById('paymentFilterDate');
    if (payDate) {
        payDate.addEventListener('change', () => {
            paymentCurrentFilter.date = payDate.value;
            fetchPayments();
        });
    }
    const btnPayToday = document.getElementById('btnPaymentFilterToday');
    if (btnPayToday) {
        btnPayToday.addEventListener('click', () => {
            const today = new Date().toISOString().split('T')[0];
            if (payDate) payDate.value = today;
            paymentCurrentFilter.date = today;
            fetchPayments();
        });
    }
    const btnPayAll = document.getElementById('btnPaymentFilterAll');
    if (btnPayAll) {
        btnPayAll.addEventListener('click', () => {
            if (payDate) payDate.value = '';
            paymentCurrentFilter.date = '';
            fetchPayments();
        });
    }
    const paySearch = document.getElementById('paymentSearchInput');
    if (paySearch) {
        let timer;
        paySearch.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                paymentCurrentFilter.search = paySearch.value.trim();
                fetchPayments();
            }, 300);
        });
    }

    // Ledger filters
    const btnLedgerFilter = document.getElementById('btnApplyLedgerFilter');
    if (btnLedgerFilter) {
        btnLedgerFilter.addEventListener('click', () => {
            const tSel = document.getElementById('ledgerFilterType');
            const fDate = document.getElementById('ledgerFilterFromDate');
            const tDate = document.getElementById('ledgerFilterToDate');
            const sInp = document.getElementById('ledgerSearchInput');

            ledgerCurrentFilter.type = tSel ? tSel.value : '';
            ledgerCurrentFilter.fromDate = fDate ? fDate.value : '';
            ledgerCurrentFilter.toDate = tDate ? tDate.value : '';
            ledgerCurrentFilter.search = sInp ? sInp.value.trim() : '';

            fetchUnifiedLedger();
        });
    }
    const btnLedgerReset = document.getElementById('btnResetLedgerFilter');
    if (btnLedgerReset) {
        btnLedgerReset.addEventListener('click', () => {
            const tSel = document.getElementById('ledgerFilterType');
            const fDate = document.getElementById('ledgerFilterFromDate');
            const tDate = document.getElementById('ledgerFilterToDate');
            const sInp = document.getElementById('ledgerSearchInput');

            if (tSel) tSel.value = '';
            if (fDate) fDate.value = '';
            if (tDate) tDate.value = '';
            if (sInp) sInp.value = '';

            ledgerCurrentFilter = { type: '', fromDate: '', toDate: '', search: '' };
            fetchUnifiedLedger();
        });
    }
}

// Hook into DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTransactionsAndLedgerEvents);
} else {
    initTransactionsAndLedgerEvents();
}


// ===========================================================================
// GATE PASS MANAGEMENT & OFFICIAL SLIP MODULE (TRI AGRO FARMS)
// ===========================================================================

let gpCurrentFilter = { pass_type: '', from_date: '', to_date: '', search: '' };
STATE.gatePasses = [];

async function fetchGatePasses() {
    const tbody = document.getElementById('gpTableBody');
    if (!tbody) return;

    let url = `${API_BASE}/api/v1/gate-pass?`;
    if (gpCurrentFilter.pass_type) url += `pass_type=${encodeURIComponent(gpCurrentFilter.pass_type)}&`;
    if (gpCurrentFilter.from_date) url += `from_date=${encodeURIComponent(gpCurrentFilter.from_date)}&`;
    if (gpCurrentFilter.to_date) url += `to_date=${encodeURIComponent(gpCurrentFilter.to_date)}&`;
    if (gpCurrentFilter.search) url += `search=${encodeURIComponent(gpCurrentFilter.search)}&`;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to load gate passes');
        const list = await res.json();
        STATE.gatePasses = list || [];

        // Update KPIs
        const kpiTotal = document.getElementById('kpiGpTotalCount');
        const kpiOut = document.getElementById('kpiGpOutwardCount');
        const kpiIn = document.getElementById('kpiGpInwardCount');
        if (kpiTotal) kpiTotal.textContent = STATE.gatePasses.length;
        if (kpiOut) kpiOut.textContent = STATE.gatePasses.filter(g => (g.pass_type || '').toLowerCase() === 'outward').length;
        if (kpiIn) kpiIn.textContent = STATE.gatePasses.filter(g => (g.pass_type || '').toLowerCase() === 'inward').length;

        renderGatePassTable(STATE.gatePasses);
    } catch (err) {
        console.error('Error fetching gate passes:', err);
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--error-red); padding: 2rem;">Error loading Gate Passes: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderGatePassTable(items) {
    const tbody = document.getElementById('gpTableBody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No Gate Passes found matching criteria.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(gp => {
        const isOut = (gp.pass_type || '').toLowerCase() === 'outward';
        const typeBadge = isOut
            ? `<span class="badge" style="background: #ECFDF5; color: #065F46; border: 1.5px solid #059669; font-weight: 700;">OUTWARD</span>`
            : `<span class="badge" style="background: #EFF6FF; color: #1E40AF; border: 1.5px solid #3B82F6; font-weight: 700;">INWARD</span>`;

        // Format items summary
        const itemsList = gp.items || [];
        let itemsSummary = '-';
        if (itemsList.length > 0) {
            itemsSummary = itemsList.map(it => `${escapeHtml(it.item_name)} (${it.quantity} ${escapeHtml(it.unit)})`).join(', ');
        }

        const driverInfo = gp.driver_name
            ? `${escapeHtml(gp.driver_name)}${gp.driver_phone ? `<br><small style="color: var(--text-muted);">${escapeHtml(gp.driver_phone)}</small>` : ''}`
            : '-';

        return `
            <tr>
                <td style="font-weight: 700; font-family: monospace;">
                    <a href="javascript:void(0)" onclick="viewGatePassSlip(${gp.id})" style="color: #064E3B; text-decoration: underline;" title="View & Print Official Slip">
                        ${escapeHtml(gp.pass_number)}
                    </a>
                </td>
                <td>${formatDate(gp.date)}</td>
                <td>${typeBadge}</td>
                <td><strong>${escapeHtml(gp.party_name || '-')}</strong></td>
                <td><span class="badge" style="background: #F1F5F9; color: var(--text-primary); font-weight: 600;">${escapeHtml(gp.vehicle_number || '-')}</span></td>
                <td>${driverInfo}</td>
                <td style="max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(itemsSummary)}">${itemsSummary}</td>
                <td style="font-size: 0.82rem; color: var(--text-muted);">${escapeHtml(gp.bilty_number || gp.reference_no || '-')}</td>
                <td style="text-align: center;">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="viewGatePassSlip(${gp.id})" style="padding: 0.25rem 0.6rem; font-size: 0.78rem; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; background: #ECFDF5; color: #065F46; border-color: #A7F3D0;" title="Print Official Slip with Logo & Signatures">
                        🖨️ Print Slip
                    </button>
                </td>
                <td style="text-align: center;">
                    <button type="button" class="btn btn-danger btn-sm" onclick="deleteGatePass(${gp.id}, '${escapeHtml(gp.pass_number)}')" style="padding: 0.2rem 0.45rem; font-size: 0.75rem; background: #DC2626; border-color: #DC2626; color: #fff;" title="Delete Gate Pass">
                        &times; Delete
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// --- GATE PASS HELPERS (Row calculation & Grand total) ---
window.updateGpRowTotal = function(elem) {
    if (!elem) return;
    const tr = elem.closest('tr');
    if (!tr) return;
    const qty = parseFloat(tr.querySelector('.gp-item-qty')?.value) || 0;
    const rate = parseFloat(tr.querySelector('.gp-item-rate')?.value) || 0;
    const totalEl = tr.querySelector('.gp-item-total');
    const total = qty * rate;
    if (totalEl) {
        totalEl.value = total > 0 ? total.toFixed(2) : '';
    }
    window.calculateGpGrandTotal();
};

window.calculateGpGrandTotal = function() {
    let grandTotal = 0;
    const rows = document.querySelectorAll('#gpItemsTableBody tr');
    rows.forEach(tr => {
        const qty = parseFloat(tr.querySelector('.gp-item-qty')?.value) || 0;
        const rate = parseFloat(tr.querySelector('.gp-item-rate')?.value) || 0;
        let total = parseFloat(tr.querySelector('.gp-item-total')?.value);
        if (isNaN(total) || total <= 0) {
            total = qty * rate;
        }
        grandTotal += (total || 0);
    });
    const totalInput = document.getElementById('gpFormTotalAmount');
    if (totalInput) {
        totalInput.value = grandTotal > 0 ? grandTotal.toFixed(2) : '';
    }
};

async function openGatePassModal(defaultDirection = 'Outward') {
    const modal = document.getElementById('modalGatePass');
    if (!modal) return;

    if (typeof window.setGatePassDirection === 'function') {
        window.setGatePassDirection(defaultDirection);
    }
    const authInput = document.getElementById('gpFormAuthorizedBy');
    if (authInput) authInput.value = 'Farm Authority';

    // Auto-fetch Next Sequential Gate Pass Number and Reference Number
    try {
        const gpCurDate = document.getElementById('gpFormDate')?.value || new Date().toISOString().split('T')[0];
        const nextRes = await fetch(`${API_BASE}/api/v1/gate-pass/next-number?date_str=${gpCurDate}`);
        if (nextRes.ok) {
            const nextData = await nextRes.json();
            const nextNum = nextData.next_pass_number || 'TA-GP-2026-NOV-000001';
            const nextRef = nextData.next_reference_no || 'TA-ref-000001';
            const passNumInput = document.getElementById('gpFormPassNumber');
            const refInput = document.getElementById('gpFormRef');
            const badgeNum = document.getElementById('gpAutoVoucherNum');
            if (passNumInput) passNumInput.value = nextNum;
            if (badgeNum) badgeNum.textContent = nextNum;
            if (refInput) {
                if (!refInput.value || refInput.value.startsWith('TA-ref-')) {
                    refInput.value = nextRef;
                }
            }
        }
    } catch (e) {
        console.warn('Could not auto-fetch next gate pass number:', e);
    }

    const today = new Date().toISOString().split('T')[0];
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const nowTime = `${hours}:${minutes}`;

    const dateInput = document.getElementById('gpFormDate');
    const timeInput = document.getElementById('gpFormTime');
    const partyInput = document.getElementById('gpFormParty');
    const phoneInput = document.getElementById('gpFormDriverPhone');
    const vehInput = document.getElementById('gpFormVehicle');
    const driverInput = document.getElementById('gpFormDriverName');
    const remarksInput = document.getElementById('gpFormRemarks');
    const totalInput = document.getElementById('gpFormTotalAmount');
    const payTypeInput = document.getElementById('gpFormPaymentType');

    if (dateInput) dateInput.value = today;
    if (timeInput) timeInput.value = nowTime;
    if (partyInput) partyInput.value = '';
    if (phoneInput) phoneInput.value = '';
    if (vehInput) vehInput.value = '';
    if (driverInput) driverInput.value = '';
    if (remarksInput) remarksInput.value = 'Fresh cut flowers dispatched in cooled temperature';
    if (totalInput) totalInput.value = '';
    if (payTypeInput) payTypeInput.value = 'Debit (Customer Ledger / Receivable)';

    // Reset items table to 1 clean flower row with all 6 columns
    const tbody = document.getElementById('gpItemsTableBody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td><input type="text" class="form-input gp-item-name" placeholder="e.g. Red Rose Stems / Fresh Gladiolus" required style="padding: 0.4rem 0.6rem; font-size: 0.88rem;"></td>
                <td><input type="number" step="0.1" min="0.1" class="form-input gp-item-qty" placeholder="50" required style="padding: 0.4rem 0.6rem; font-size: 0.88rem; text-align: center; font-weight: 700;" oninput="window.updateGpRowTotal(this)"></td>
                <td>
                    <select class="form-select gp-item-unit" style="padding: 0.4rem 0.6rem; font-size: 0.88rem; font-weight: 600;">
                        <option value="Bunches">Bunches</option>
                        <option value="Stems">Stems</option>
                        <option value="Boxes">Boxes</option>
                        <option value="Crates">Crates</option>
                        <option value="Buckets">Buckets</option>
                        <option value="Kg">Kg</option>
                        <option value="Pcs">Pcs</option>
                    </select>
                </td>
                <td><input type="number" step="0.01" min="0" class="form-input gp-item-rate" placeholder="500" style="padding: 0.4rem 0.6rem; font-size: 0.88rem; text-align: right;" oninput="window.updateGpRowTotal(this)"></td>
                <td><input type="number" step="0.01" class="form-input gp-item-total" placeholder="25000" style="padding: 0.4rem 0.6rem; font-size: 0.88rem; text-align: right; font-weight: 700; background: #F8FAFC;" readonly></td>
                <td style="text-align: center;"><button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove(); window.calculateGpGrandTotal();" style="padding: 0.2rem 0.45rem; font-size: 0.75rem;">&times;</button></td>
            </tr>
        `;
    }

    modal.removeAttribute('hidden');
}

function addGatePassItemRow() {
    const tbody = document.getElementById('gpItemsTableBody');
    if (!tbody) return;
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="form-input gp-item-name" placeholder="e.g. Red Rose Stems / Fresh Gladiolus / Marigold Bunches" required style="padding: 0.4rem 0.6rem; font-size: 0.88rem;"></td>
        <td><input type="number" step="0.1" min="0.1" class="form-input gp-item-qty" placeholder="25" required style="padding: 0.4rem 0.6rem; font-size: 0.88rem; text-align: center; font-weight: 700;" oninput="window.updateGpRowTotal(this)"></td>
        <td>
            <select class="form-select gp-item-unit" style="padding: 0.4rem 0.6rem; font-size: 0.88rem; font-weight: 600;">
                <option value="Bunches">Bunches</option>
                <option value="Stems">Stems</option>
                <option value="Boxes">Boxes</option>
                <option value="Crates">Crates</option>
                <option value="Buckets">Buckets</option>
                <option value="Kg">Kg</option>
                <option value="Pcs">Pcs</option>
            </select>
        </td>
        <td><input type="number" step="0.01" min="0" class="form-input gp-item-rate" placeholder="500" style="padding: 0.4rem 0.6rem; font-size: 0.88rem; text-align: right;" oninput="window.updateGpRowTotal(this)"></td>
        <td><input type="number" step="0.01" class="form-input gp-item-total" placeholder="12500" style="padding: 0.4rem 0.6rem; font-size: 0.88rem; text-align: right; font-weight: 700; background: #F8FAFC;" readonly></td>
        <td style="text-align: center;"><button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove(); window.calculateGpGrandTotal();" style="padding: 0.2rem 0.45rem; font-size: 0.75rem;">&times;</button></td>
    `;
    tbody.appendChild(tr);
}

async function handleGatePassSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSubmitGatePass');
    if (btn) btn.disabled = true;

    try {
        const pType = document.getElementById('gpFormType')?.value || 'Outward';
        const pDate = document.getElementById('gpFormDate')?.value;
        const pTime = document.getElementById('gpFormTime')?.value?.trim() || '';
        const pParty = document.getElementById('gpFormParty')?.value?.trim() || '';
        const pPhone = document.getElementById('gpFormDriverPhone')?.value?.trim() || '';
        const pVehicle = document.getElementById('gpFormVehicle')?.value?.trim() || '';
        const pDriver = document.getElementById('gpFormDriverName')?.value?.trim() || '';
        const pRemarks = document.getElementById('gpFormRemarks')?.value?.trim() || 'Fresh flowers dispatched in verified condition';

        if (!pParty) throw new Error('Please enter Order Received By (Customer / Florist name).');
        if (!pPhone) throw new Error('Please enter Receiver Contact / Phone Number.');

        // Collect items
        const rows = document.querySelectorAll('#gpItemsTableBody tr');
        const items = [];
        let itemsSum = 0;
        rows.forEach(tr => {
            const name = tr.querySelector('.gp-item-name')?.value.trim();
            const qty = parseFloat(tr.querySelector('.gp-item-qty')?.value) || 0;
            const unit = tr.querySelector('.gp-item-unit')?.value || 'Bunches';
            const rate = parseFloat(tr.querySelector('.gp-item-rate')?.value) || 0;
            const amount = parseFloat(tr.querySelector('.gp-item-total')?.value) || (qty * rate);
            if (name && qty > 0) {
                itemsSum += amount;
                items.push({
                    item_name: name,
                    quality: 'Fresh Export Quality',
                    quantity: qty,
                    unit: unit,
                    rate: rate,
                    amount: amount,
                    remarks: 'Verified Fresh Flowers'
                });
            }
        });

        if (items.length === 0) {
            throw new Error('Please enter at least 1 flower product and quantity.');
        }

        const formTotal = parseFloat(document.getElementById('gpFormTotalAmount')?.value);
        const totalAmount = (!isNaN(formTotal) && formTotal > 0) ? formTotal : itemsSum;
        const paymentType = document.getElementById('gpFormPaymentType')?.value || 'Debit (Customer Ledger / Receivable)';

        // Combine date and time
        let combinedDate = new Date();
        if (pDate) {
            if (pTime) {
                combinedDate = new Date(`${pDate}T${pTime}:00`);
            } else {
                combinedDate = new Date(pDate);
            }
        }

        const payload = {
            date: combinedDate.toISOString(),
            pass_type: pType,
            party_name: pParty,
            vehicle_number: pVehicle || 'Flower Delivery Courier',
            driver_name: pDriver || null,
            driver_phone: pPhone,
            pass_number: document.getElementById('gpFormPassNumber')?.value.trim() || undefined,
            bilty_number: null,
            reference_no: document.getElementById('gpFormRef')?.value.trim() || (pTime ? `Time: ${pTime}` : null),
            total_amount: totalAmount,
            payment_type: paymentType,
            items: items,
            remarks: pRemarks,
            prepared_by: 'Muhammad Saad',
            gate_incharge: 'Gate Security Office',
            authorized_by: 'Farm Authority'
        };

        const res = await fetch(`${API_BASE}/api/v1/gate-pass`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to generate Gate Pass');
        }

        const created = await res.json();
        alert(`Farm Gate Pass ${created.pass_number} generated successfully!`);

        const modal = document.getElementById('modalGatePass');
        if (modal) modal.setAttribute('hidden', '');

        await fetchGatePasses();

        // Immediately open the official printable Gate Pass slip
        viewGatePassSlip(created.id);
    } catch (err) {
        alert(err.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function viewGatePassSlip(gpId) {
    try {
        const res = await fetch(`${API_BASE}/api/v1/gate-pass/${gpId}`);
        if (!res.ok) throw new Error('Failed to load Gate Pass slip');
        const gp = await res.json();

        // Populate company branding from profile
        if (STATE.profile) {
            const cName = document.getElementById('gpSlipCompanyName');
            const cAddr = document.getElementById('gpSlipCompanyAddress');
            if (cName) cName.textContent = STATE.profile.company_name || 'Tri Agro Farms';
            if (cAddr) cAddr.textContent = `${STATE.profile.address || 'Sheikhupura'} • Phone: ${STATE.profile.phone || '0320944803'}`;
        }

        // Populate header & badge
        const badge = document.getElementById('gpSlipTypeBadge');
        const isOut = (gp.pass_type || '').toLowerCase() === 'outward';
        if (badge) {
            badge.textContent = isOut ? 'STOCK OUT (FLOWER DISPATCH)' : 'STOCK IN (FLOWER RECEIVING)';
            badge.style.background = isOut ? '#ECFDF5' : '#EFF6FF';
            badge.style.color = isOut ? '#065F46' : '#1E40AF';
            badge.style.borderColor = isOut ? '#059669' : '#3B82F6';
        }

        const slipNum = document.getElementById('gpSlipNumber');
        const slipRef = document.getElementById('gpSlipReference');
        if (slipRef) slipRef.textContent = gp.reference_no || '-';
        const slipDate = document.getElementById('gpSlipDate');
        const slipTime = document.getElementById('gpSlipTime');
        const slipParty = document.getElementById('gpSlipParty');
        const slipReceiverPhone = document.getElementById('gpSlipReceiverPhone');
        const slipVeh = document.getElementById('gpSlipVehicle');
        const slipPreparedBy = document.getElementById('gpSlipPreparedBy');
        const slipRemarks = document.getElementById('gpSlipRemarks');
        const itemsBody = document.getElementById('gpSlipItemsBody');
        const slipReceiver = document.getElementById('gpSlipReceiver');
        const slipReceiverSigSub = document.getElementById('gpSlipReceiverSigSub');
        const slipAuthorizedBy = document.getElementById('gpSlipAuthorizedBy');
        const slipTotalAmount = document.getElementById('gpSlipTotalAmount');
        const slipPaymentType = document.getElementById('gpSlipPaymentType');
        const footQty = document.getElementById('gpSlipFootQty');
        const footAmount = document.getElementById('gpSlipFootAmount');

        if (slipNum) slipNum.textContent = gp.pass_number;
        if (slipDate) slipDate.textContent = formatDate(gp.date);
        
        let displayTime = '';
        if (gp.reference_no && gp.reference_no.includes('Time:')) {
            displayTime = gp.reference_no.replace('Time:', '').trim();
        } else if (gp.date) {
            displayTime = new Date(gp.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
        }
        if (slipTime) slipTime.textContent = displayTime || '-';

        if (slipParty) slipParty.textContent = gp.party_name || '-';
        if (slipReceiverPhone) slipReceiverPhone.textContent = gp.driver_phone || '-';
        if (slipVeh) slipVeh.textContent = gp.vehicle_number || '-';
        if (slipPreparedBy) slipPreparedBy.textContent = gp.prepared_by || 'Tri Agro Farms Dispatch';
        if (slipRemarks) slipRemarks.textContent = gp.remarks || 'Fresh flowers dispatched in verified condition';

        // Blank signatures for real physical pen signing
        if (slipReceiver) {
            slipReceiver.textContent = gp.party_name ? `${gp.party_name} (Receiver)` : 'Receiver Signature';
        }
        if (slipReceiverSigSub) {
            slipReceiverSigSub.textContent = gp.driver_phone ? `Receiver Contact: ${gp.driver_phone}` : 'Customer / Driver Signature';
        }
        if (slipAuthorizedBy) {
            slipAuthorizedBy.textContent = 'Authorized Signature';
        }

        // Populate items table with all 6 columns
        let totalQty = 0;
        let totalAmountCalc = 0;

        if (itemsBody) {
            itemsBody.innerHTML = (gp.items || []).map((it, idx) => {
                const qty = Number(it.quantity || 0);
                const rate = Number(it.rate || 0);
                const amt = Number(it.amount || (qty * rate));
                totalQty += qty;
                totalAmountCalc += amt;
                return `
                    <tr style="border-bottom: 1px solid #CBD5E1;">
                        <td style="padding: 9px 12px; border: 1px solid #CBD5E1; text-align: center; font-weight: 700;">${idx + 1}</td>
                        <td style="padding: 9px 12px; font-weight: 700; border: 1px solid #CBD5E1; color: #0F172A; font-size: 0.95rem;">${escapeHtml(it.item_name)}</td>
                        <td style="padding: 9px 12px; text-align: right; font-weight: 800; border: 1px solid #CBD5E1; color: #064E3B;">${qty.toLocaleString()}</td>
                        <td style="padding: 9px 12px; text-align: center; font-weight: 600; border: 1px solid #CBD5E1; color: #475569;">${escapeHtml(it.unit || 'Bunches')}</td>
                        <td style="padding: 9px 12px; text-align: right; font-weight: 600; border: 1px solid #CBD5E1; color: #0F172A;">${rate > 0 ? rate.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '-'}</td>
                        <td style="padding: 9px 12px; text-align: right; font-weight: 800; border: 1px solid #CBD5E1; color: #064E3B;">${amt > 0 ? amt.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '-'}</td>
                    </tr>
                `;
            }).join('');
        }

        const grandFinal = (gp.total_amount && gp.total_amount > 0) ? gp.total_amount : totalAmountCalc;
        if (slipTotalAmount) {
            slipTotalAmount.textContent = `PKR ${grandFinal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        if (slipPaymentType) {
            slipPaymentType.textContent = gp.payment_type || 'Debit (Customer Ledger / Receivable)';
        }
        if (footQty) {
            footQty.textContent = `${totalQty.toLocaleString()} Total Units`;
        }
        if (footAmount) {
            footAmount.textContent = `PKR ${grandFinal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }

        const modal = document.getElementById('modalGatePassSlip');
        if (modal) modal.removeAttribute('hidden');
    } catch (err) {
        alert(err.message);
    }
}

async function deleteGatePass(id, passNum) {
    if (!confirm(`Are you sure you want to delete Gate Pass "${passNum}"?\\n\\nThis record will be permanently removed.`)) {
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/v1/gate-pass/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete Gate Pass');
        alert(`Gate Pass ${passNum} deleted successfully.`);
        await fetchGatePasses();
    } catch (err) {
        alert(err.message);
    }
}

window.openGatePassModal = openGatePassModal;
window.viewGatePassSlip = viewGatePassSlip;
window.deleteGatePass = deleteGatePass;
window.addGatePassItemRow = addGatePassItemRow;

function initGatePassEvents() {
    const btnOpen = document.getElementById('btnOpenGatePassModal');
    if (btnOpen) btnOpen.addEventListener('click', () => openGatePassModal('Outward'));

    const btnOpenIn = document.getElementById('btnOpenGpStockIn');
    if (btnOpenIn) btnOpenIn.addEventListener('click', () => openGatePassModal('Inward'));

    const btnOpenOut = document.getElementById('btnOpenGpStockOut');
    if (btnOpenOut) btnOpenOut.addEventListener('click', () => openGatePassModal('Outward'));

    // Stock IN and Stock OUT Action Buttons Wiring
    const btnStockIn = document.getElementById('btnGpStockIn');
    const btnStockOut = document.getElementById('btnGpStockOut');
    const typeInput = document.getElementById('gpFormType');

    function setGpDirection(dir) {
        if (!typeInput) return;
        typeInput.value = dir;
        if (dir === 'Inward') {
            if (btnStockIn) {
                btnStockIn.style.background = '#059669';
                btnStockIn.style.color = '#fff';
                btnStockIn.style.borderColor = '#059669';
                btnStockIn.style.boxShadow = '0 2px 6px rgba(5,150,105,0.3)';
            }
            if (btnStockOut) {
                btnStockOut.style.background = '#F8FAFC';
                btnStockOut.style.color = '#64748B';
                btnStockOut.style.borderColor = '#CBD5E1';
                btnStockOut.style.boxShadow = 'none';
            }
        } else {
            if (btnStockOut) {
                btnStockOut.style.background = '#2563EB';
                btnStockOut.style.color = '#fff';
                btnStockOut.style.borderColor = '#2563EB';
                btnStockOut.style.boxShadow = '0 2px 6px rgba(37,99,235,0.3)';
            }
            if (btnStockIn) {
                btnStockIn.style.background = '#F8FAFC';
                btnStockIn.style.color = '#64748B';
                btnStockIn.style.borderColor = '#CBD5E1';
                btnStockIn.style.boxShadow = 'none';
            }
        }
    }

    if (btnStockIn) btnStockIn.addEventListener('click', () => setGpDirection('Inward'));
    if (btnStockOut) btnStockOut.addEventListener('click', () => setGpDirection('Outward'));
    window.setGatePassDirection = setGpDirection;

    const btnAddItem = document.getElementById('btnGpAddItem');
    if (btnAddItem) btnAddItem.addEventListener('click', addGatePassItemRow);

    const form = document.getElementById('formAddGatePass');
    if (form) form.addEventListener('submit', handleGatePassSubmit);

    const tabs = document.getElementById('gpTypeTabs');
    if (tabs) {
        tabs.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                gpCurrentFilter.pass_type = tab.getAttribute('data-gptype') || '';
                fetchGatePasses();
            });
        });
    }

    const dateFilter = document.getElementById('gpFilterDate');
    if (dateFilter) {
        dateFilter.addEventListener('change', () => {
            gpCurrentFilter.from_date = dateFilter.value;
            gpCurrentFilter.to_date = dateFilter.value;
            fetchGatePasses();
        });
    }
    const btnToday = document.getElementById('btnGpFilterToday');
    if (btnToday) {
        btnToday.addEventListener('click', () => {
            const today = new Date().toISOString().split('T')[0];
            if (dateFilter) dateFilter.value = today;
            gpCurrentFilter.from_date = today;
            gpCurrentFilter.to_date = today;
            fetchGatePasses();
        });
    }
    const btnAll = document.getElementById('btnGpFilterAll');
    if (btnAll) {
        btnAll.addEventListener('click', () => {
            if (dateFilter) dateFilter.value = '';
            gpCurrentFilter.from_date = '';
            gpCurrentFilter.to_date = '';
            fetchGatePasses();
        });
    }

    const searchInput = document.getElementById('gpSearchInput');
    if (searchInput) {
        let timer;
        searchInput.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                gpCurrentFilter.search = searchInput.value.trim();
                fetchGatePasses();
            }, 300);
        });
    }

    // Auto-fetch and render gate pass entries on initialization
    fetchGatePasses();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGatePassEvents);
} else {
    initGatePassEvents();
}


async function deleteIncomeTransaction(incomeId, txNum) {
    const tName = txNum || `Income #${incomeId}`;
    if (!confirm(`Are you sure you want to permanently delete income transaction ${tName}?\n\nThis will delete the transaction, reverse associated accounts, and restore customer balance allocations.`)) {
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/v1/income/${incomeId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to delete income transaction');
        }
        alert(`${tName} has been permanently deleted and balances reversed.`);
        await Promise.all([
            fetchIncomes(),
            fetchDashboardSummary(),
            fetchAccounts(),
            fetchParties()
        ]);
    } catch (err) {
        alert('Error deleting income: ' + err.message);
    }
}
window.deleteIncomeTransaction = deleteIncomeTransaction;

// --- Native Screen-Identical Single-Page Slip Printing Handlers ---
function printVoucherSlipNow() {
    document.body.classList.add('printing-voucher');
    document.body.classList.remove('printing-gate-pass');

    const origTitle = document.title;
    const vNum = (DOM.slipVoucherNumber && DOM.slipVoucherNumber.textContent) ? DOM.slipVoucherNumber.textContent.trim() : '';
    if (vNum && vNum !== '-') {
        document.title = `Voucher_${vNum}`;
    }

    void document.body.offsetHeight;

    setTimeout(() => {
        window.print();
        setTimeout(() => {
            document.body.classList.remove('printing-voucher');
            document.title = origTitle;
        }, 500);
    }, 80);
}

function printGatePassSlipNow() {
    document.body.classList.add('printing-gate-pass');
    document.body.classList.remove('printing-voucher');

    const origTitle = document.title;
    const gpNum = document.getElementById('gpSlipNumber') ? document.getElementById('gpSlipNumber').textContent.trim() : '';
    if (gpNum && gpNum !== '-') {
        document.title = `GatePass_${gpNum}`;
    }

    void document.body.offsetHeight;

    setTimeout(() => {
        window.print();
        setTimeout(() => {
            document.body.classList.remove('printing-gate-pass');
            document.title = origTitle;
        }, 500);
    }, 80);
}

window.addEventListener('beforeprint', () => {
    const gpModal = document.getElementById('modalGatePassSlip');
    if (gpModal && !gpModal.hasAttribute('hidden')) {
        document.body.classList.add('printing-gate-pass');
        document.body.classList.remove('printing-voucher');
    }
    const vModal = document.getElementById('modalVoucherSlip');
    if (vModal && !vModal.hasAttribute('hidden')) {
        document.body.classList.add('printing-voucher');
        document.body.classList.remove('printing-gate-pass');
    }
});

window.addEventListener('afterprint', () => {
    document.body.classList.remove('printing-gate-pass');
    document.body.classList.remove('printing-voucher');
});

window.printGatePassSlipNow = printGatePassSlipNow;
window.printVoucherSlipNow = printVoucherSlipNow;


// ---------------------------------------------------------------------------
// VIEW 6: SETTINGS TABS & CUSTOMER FORM CUSTOM FIELDS
// ---------------------------------------------------------------------------
function switchSettingsTab(tabKey) {
    const tabs = ['profile', 'customFields', 'quickLinks'];
    tabs.forEach(t => {
        const cap = t.charAt(0).toUpperCase() + t.slice(1);
        const btn = document.getElementById(`tabBtnSettings${cap}`);
        const pane = document.getElementById(`tabContentSettings${cap}`);
        if (btn) btn.classList.toggle('active', t === tabKey);
        if (pane) pane.style.display = t === tabKey ? 'block' : 'none';
    });
    if (tabKey === 'customFields') {
        fetchCustomFields();
    }
}

async function fetchCustomFields() {
    const tbody = document.getElementById('customFieldsTableBody');
    if (!tbody) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/custom_fields/`);
        if (!res.ok) {
            throw new Error('Failed to load custom fields.');
        }
        const fields = await res.json();
        STATE.customFields = fields;
        renderCustomFieldsTable(fields);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #DC2626; padding: 1.5rem;">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderCustomFieldsTable(fields) {
    const tbody = document.getElementById('customFieldsTableBody');
    if (!tbody) return;
    if (!fields || fields.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: #64748B;">No custom fields created yet. Click "+ Add Custom Field" above to configure your first customer field (e.g. NTN, CNIC, Delivery Route).</td></tr>`;
        return;
    }

    tbody.innerHTML = fields.map(f => `
        <tr>
            <td style="font-weight: 700; color: #0F172A;">${escapeHtml(f.label)}</td>
            <td><code>${escapeHtml(f.name)}</code></td>
            <td><span class="badge" style="background: #EFF6FF; color: #1D4ED8; font-weight: 600; padding: 2px 8px; border-radius: 4px; text-transform: capitalize;">${escapeHtml(f.field_type)}</span></td>
            <td>${f.required ? '<span style="color: #DC2626; font-weight: 700;">Yes</span>' : '<span style="color: #64748B;">Optional</span>'}</td>
            <td>${f.options ? escapeHtml(f.options) : '<span style="color: #94A3B8;">&mdash;</span>'}</td>
            <td style="text-align: right;">
                <button type="button" class="btn btn-sm" onclick="deleteCustomField(${f.id}, '${escapeHtml(f.label)}')" style="background: #FEE2E2; color: #DC2626; border: 1px solid #FECACA; padding: 3px 8px; font-size: 0.8rem; border-radius: 4px; cursor: pointer;">
                    🗑️ Delete
                </button>
            </td>
        </tr>
    `).join('');
}

function showAddCustomFieldModal() {
    const modal = document.getElementById('modalAddCustomField');
    const form = document.getElementById('formAddCustomField');
    if (form) form.reset();
    const optGroup = document.getElementById('cfOptionsGroup');
    if (optGroup) optGroup.style.display = 'none';
    if (modal) modal.removeAttribute('hidden');
}

function toggleCfOptionsInput(fieldType) {
    const optGroup = document.getElementById('cfOptionsGroup');
    if (optGroup) {
        optGroup.style.display = fieldType === 'select' ? 'block' : 'none';
    }
}

async function handleAddCustomField(e) {
    e.preventDefault();
    const labelInput = document.getElementById('cfInputLabel');
    const nameInput = document.getElementById('cfInputName');
    const typeInput = document.getElementById('cfInputType');
    const reqInput = document.getElementById('cfInputRequired');
    const optInput = document.getElementById('cfInputOptions');
    const alertBanner = document.getElementById('customFieldAlertBanner');

    const label = labelInput ? labelInput.value.trim() : '';
    let name = nameInput ? nameInput.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_') : '';
    const fieldType = typeInput ? typeInput.value : 'text';
    const isRequired = reqInput ? reqInput.checked : false;
    const rawOptions = optInput ? optInput.value.trim() : '';

    if (!label) {
        alert('Please provide a field label.');
        return;
    }
    if (!name) {
        name = label.toLowerCase().replace(/[^a-z0-9_]/g, '_');
    }

    const payload = {
        name: name,
        label: label,
        field_type: fieldType,
        required: isRequired,
        enabled: true,
        options: (fieldType === 'select' && rawOptions) ? rawOptions.split(',').map(s => s.trim()).filter(Boolean) : null
    };

    try {
        const res = await fetch(`${API_BASE}/api/v1/custom_fields/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to create custom field.');
        }

        const modal = document.getElementById('modalAddCustomField');
        if (modal) modal.setAttribute('hidden', '');

        if (alertBanner) {
            alertBanner.style.display = 'block';
            alertBanner.className = 'diff-badge balanced';
            alertBanner.textContent = `✓ Custom field "${label}" successfully added to Customer Form!`;
            setTimeout(() => { alertBanner.style.display = 'none'; }, 5000);
        }

        await fetchCustomFields();
    } catch (err) {
        alert(err.message || 'Error adding custom field.');
    }
}

async function deleteCustomField(id, label) {
    if (!confirm(`Are you sure you want to delete the custom field "${label}"? This will remove it from all future customer forms.`)) {
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/v1/custom_fields/${id}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to delete custom field.');
        }
        await fetchCustomFields();
    } catch (err) {
        alert(err.message || 'Error deleting custom field.');
    }
}

window.switchSettingsTab = switchSettingsTab;
window.showAddCustomFieldModal = showAddCustomFieldModal;
window.toggleCfOptionsInput = toggleCfOptionsInput;
window.deleteCustomField = deleteCustomField;


// Offline & Online Synchronization Listeners
window.addEventListener('online', () => {
    if (DOM.systemStatusText) {
        DOM.systemStatusText.innerHTML = `Reconnected &bull; Synchronizing...`;
    }
    autoSyncOfflineQueue(false);
});

window.addEventListener('offline', () => {
    updateOfflineStatusUI();
});

// Auto-update Voucher sequence number when Transaction Date changes
async function updateVoucherSequenceOnDateChange() {
    if (!DOM.vFormDate) return;
    try {
        const dVal = DOM.vFormDate.value;
        const res = await fetch(`${API_BASE}/api/v1/vouchers/next-sequence?date=${dVal}`);
        if (res.ok) {
            const seq = await res.json();
            if (DOM.vFormVoucherNumber) DOM.vFormVoucherNumber.value = seq.next_voucher_number;
            if (DOM.vFormRef && (!DOM.vFormRef.value || DOM.vFormRef.value.startsWith('TA-ref-'))) {
                DOM.vFormRef.value = seq.next_reference_no;
            }
        }
    } catch (e) {
        console.warn('Could not update sequence on date change:', e);
    }
}

// Auto-update Gate Pass sequence number when Gate Pass Date changes
async function updateGatePassSequenceOnDateChange() {
    const gpDateInput = document.getElementById('gpFormDate');
    if (!gpDateInput) return;
    try {
        const dVal = gpDateInput.value;
        const res = await fetch(`${API_BASE}/api/v1/gate-pass/next-number?date_str=${dVal}`);
        if (res.ok) {
            const seq = await res.json();
            const passNumInput = document.getElementById('gpFormPassNumber');
            const badgeNum = document.getElementById('gpAutoVoucherNum');
            const refInput = document.getElementById('gpFormRef');
            if (passNumInput) passNumInput.value = seq.next_pass_number;
            if (badgeNum) badgeNum.textContent = seq.next_pass_number;
            if (refInput && (!refInput.value || refInput.value.startsWith('TA-ref-'))) {
                refInput.value = seq.next_reference_no;
            }
        }
    } catch (e) {
        console.warn('Could not update gate pass sequence on date change:', e);
    }
}

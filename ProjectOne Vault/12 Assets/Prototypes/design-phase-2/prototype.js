/* ==========================================================================
   ProjectOne — the product blueprint

   THIS IS NOT THE APPLICATION.
   No network, no framework, no build step, no external dependency, no storage
   beyond a single theme preference. Every name, number, timestamp and piece of
   media in it is invented, and every one of them is drawn rather than fetched.

   WHAT THIS FILE IS. The core: utilities, the fake server payload, the router,
   the shell, the overlay system and the shared components. The screens live in
   `screens.js` and register themselves into `PO.views`.

   THE ONE RULE THIS PROTOTYPE HOLDS ITSELF TO. It never DERIVES a permission,
   a cost or a legal transition on the client. It renders what the payload
   says, exactly as the real application does — because a prototype that
   computes `canApprove` in the browser is teaching the wrong architecture to
   whoever implements it next.
   ========================================================================== */
'use strict';

var PO = window.PO = window.PO || {};
PO.views = PO.views || {};

(function () {

  /* ---------------------------------------------------------------- utils */
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  var icon = function (name, cls) {
    return '<svg class="' + (cls || 'icon') + '" aria-hidden="true"><use href="#i-' + name + '"/></svg>';
  };
  var money = function (n) {
    return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  var money3 = function (n) { return '$' + Number(n).toFixed(3); };
  var num = function (n) { return Number(n).toLocaleString('en-US'); };
  var plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };

  /* Annotations are out-of-flow by construction: an `outline` plus an
     absolutely-positioned badge. Turning them on moves zero pixels, which is
     the only way a provenance layer can be trusted not to change the design
     it is annotating. */
  var ANNO_LABEL = { existing: 'Available now', planned: 'On the plan', proposed: 'Proposed', sim: 'Simulated' };
  var anno = function (kind, note) {
    return ' data-anno="' + kind + '" data-anno-label="' + esc(ANNO_LABEL[kind] + (note ? ' · ' + note : '')) + '"';
  };

  /* ================================================================== data */

  /* The one workflow this deployment can actually run. Three steps, the
     middle one gated. Everything the run screens show about it is true. */
  var WORKFLOW = {
    key: 'project_planning', name: 'Project planning', version: 1,
    steps: [
      { index: 0, name: 'Validate project', kind: 'deterministic', requires_approval: false,
        purpose: 'Checks the project has a brief, a target format and an audience before any AI call is made.',
        touches: 'Reads the project record. Writes nothing. Spends nothing.' },
      { index: 1, name: 'Planning agent', kind: 'ai', requires_approval: true,
        purpose: 'Drafts a structured production plan from the brief: an outline, a running order and a hook per item.',
        touches: 'Sends the brief to the configured provider and writes one draft plan into this project. Nothing is published anywhere.' },
      { index: 2, name: 'Quality check', kind: 'deterministic', requires_approval: false,
        purpose: 'Scores the draft against the workflow’s completeness rules and flags gaps.',
        touches: 'Reads the draft. Writes a score onto the run. Spends nothing.' }
    ]
  };

  var C = PO.CAMPAIGN;

  var DATA = {
    user: { id: 'u_avery', name: 'Avery Kim', email: 'avery@averykim.studio', initials: 'AK', role: 'Owner' },
    workspace: { id: 'ws_7ac1', name: 'Avery Kim Studio', created: '4 March 2026', plan: 'Studio' },

    /* Server-supplied. The client NEVER computes these. */
    permissions: {
      role: 'owner', can_start_run: true, can_approve: true, can_manage_budget: true,
      can_manage_members: true, denied_reason: null
    },

    members: [
      { id: 'u_avery', name: 'Avery Kim', email: 'avery@averykim.studio', initials: 'AK', role: 'owner', joined: '4 March 2026', craft: 'Creator' },
      { id: 'u_noor', name: 'Noor Haddad', email: 'noor@averykim.studio', initials: 'NH', role: 'admin', joined: '18 April 2026', craft: 'Producer' },
      { id: 'u_diego', name: 'Diego Salas', email: 'diego@averykim.studio', initials: 'DS', role: 'member', joined: '2 June 2026', craft: 'Editor' },
      { id: 'u_priya', name: 'Priya Raman', email: 'priya@averykim.studio', initials: 'PR', role: 'member', joined: '2 June 2026', craft: 'Design' }
    ],

    budget: {
      limit_usd: 2000.00, spent_usd: 1284.60, period_days: 30,
      breaker_open: false, breaker_reason: null, period_label: '1–21 August 2026'
    },

    providers: [
      { id: 'anthropic', label: 'Anthropic', model: 'claude-sonnet-4-5', last_four: '4d1c', role: 'Primary', health: 'healthy', added: '4 March 2026' },
      { id: 'openai', label: 'OpenAI', model: 'gpt-4.1-mini', last_four: '9f27', role: 'Fallback', health: 'healthy', added: '11 March 2026' }
    ],

    projects: [
      { id: 'p_kc2', key: 'K', name: 'Kitchen Confidence — Season Two', status: 'generation',
        brief: 'Six episodes, one intimidating technique each, for cooks who already own the pans but not the nerve. The season lives or dies on the trailer.',
        campaign: true, launch: '14 September', days_out: 9,
        audience: 'Home cooks who own the pans but not the nerve',
        assets: ['as_trailer', 'as_b30', 'as_sear', 'as_rise', 'as_carousel', 'as_keyart', 'as_titles',
                 'as_ad_meta', 'as_ad_story', 'as_ad_tiktok', 'as_ad_preroll', 'as_ad_display', 'as_ad_copy',
                 'as_script', 'as_email', 'as_caps', 'as_selects', 'as_outline'],
        people: ['u_avery', 'u_noor', 'u_diego', 'u_priya'],
        spent: 486.20, updated: 'Updated 12 minutes ago', scene: 'sear',
        legal_transitions: ['review', 'archive'] },
      { id: 'p_pantry', key: 'P', name: 'The 20-Minute Pantry', status: 'planning',
        brief: 'Short-form series built entirely from shelf-stable ingredients, aimed at the weeknight audience that bounced off Season One.',
        audience: 'Weeknight cooks who bounced off Season One',
        assets: [], people: ['u_avery', 'u_noor'], spent: 12.40,
        updated: 'Updated 2 hours ago', scene: 'over',
        legal_transitions: ['generation', 'archive'] },
      { id: 'p_castiron', key: 'C', name: 'Cast Iron, Explained', status: 'review',
        brief: 'One long-form explainer answering the twelve cast-iron questions that fill the comments on every other video.',
        audience: 'The commenters who ask the same twelve questions',
        assets: ['as_selects'], people: ['u_avery', 'u_diego'], spent: 61.05,
        updated: 'Updated yesterday', scene: 'knife',
        legal_transitions: ['editing', 'archive'] },
      { id: 'p_sour', key: 'S', name: 'Sourdough Without the Cult', status: 'archive',
        brief: 'A plain-language starter guide with none of the ritual. Parked after the format test underperformed.',
        audience: 'Beginners put off by sourdough ritual',
        assets: ['as_outline'], people: ['u_avery'], spent: 8.90,
        updated: 'Updated 11 days ago', scene: 'loaf',
        legal_transitions: ['idea'] }
    ],

    runs: [
      { id: 'r_1042', title: 'Season Two — episode plan', project_id: 'p_kc2',
        workflow: 'project_planning', version: 1, status: 'awaiting_approval',
        started: 'Today, 09:04', finished: null, tokens: 0, cost: 0.000, by: 'u_avery', seeded: true,
        steps: [
          { index: 0, status: 'completed', detail: 'Brief, target format and audience all present. 12 assets attached to the project.', tokens: 0, cost: 0, started: '09:04:11', finished: '09:04:11', duration: '0.4s' },
          { index: 1, status: 'awaiting_approval', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null },
          { index: 2, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null }
        ] },
      { id: 'r_1041', title: 'Pantry — running order', project_id: 'p_pantry',
        workflow: 'project_planning', version: 1, status: 'running',
        started: 'Today, 09:08', finished: null, tokens: 0, cost: 0.000, by: 'u_noor', seeded: true,
        approved_note: 'Planning agent approved by Avery Kim at 09:12.',
        steps: [
          { index: 0, status: 'completed', detail: 'Brief and target format present. Audience inferred from the project brief.', tokens: 0, cost: 0, started: '09:08:02', finished: '09:08:03', duration: '0.6s' },
          { index: 1, status: 'running', detail: 'Drafting the running order.', tokens: null, cost: null, started: '09:12:40', finished: null, duration: null },
          { index: 2, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null }
        ] },
      { id: 'r_1039', title: 'Cast Iron — explainer plan', project_id: 'p_castiron',
        workflow: 'project_planning', version: 1, status: 'failed',
        started: 'Yesterday, 17:31', finished: 'Yesterday, 17:33', tokens: 0, cost: 0.000, by: 'u_avery', seeded: true,
        failure: {
          headline: 'The AI provider did not respond, and the fallback did not either.',
          plain: 'Anthropic returned “overloaded” three times in a row. ProjectOne then tried OpenAI, which timed out twice. After five attempts across two providers the run stopped instead of continuing to retry.',
          why_stopped: 'This is the retry ceiling doing its job. Retrying forever is how an AI feature turns into an unbounded bill, so the run stops and waits for you.',
          technical: 'step=1 name="Planning agent"\nattempt 1  anthropic/claude-sonnet-4-5   HTTP 529 overloaded_error\nattempt 2  anthropic/claude-sonnet-4-5   HTTP 529 overloaded_error\nattempt 3  anthropic/claude-sonnet-4-5   HTTP 529 overloaded_error\nfallback -> openai/gpt-4.1-mini\nattempt 4  openai/gpt-4.1-mini           timeout after 60s\nattempt 5  openai/gpt-4.1-mini           timeout after 60s\nretry ceiling reached (3 attempts x 2 providers) -> run marked failed',
          billed: 'No completion was returned, so nothing was metered against your budget for this step.'
        },
        steps: [
          { index: 0, status: 'completed', detail: 'Brief, target format and audience all present. 5 assets attached.', tokens: 0, cost: 0, started: '17:31:44', finished: '17:31:45', duration: '0.5s' },
          { index: 1, status: 'failed', detail: 'Provider unavailable after 5 attempts across 2 providers.', tokens: 0, cost: 0, started: '17:31:45', finished: '17:33:02', duration: '1m 17s' },
          { index: 2, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null }
        ] },
      { id: 'r_1035', title: 'Sourdough — starter guide plan', project_id: 'p_sour',
        workflow: 'project_planning', version: 1, status: 'completed',
        started: '10 Aug, 14:20', finished: '10 Aug, 14:22', tokens: 6940, cost: 0.112, by: 'u_avery', seeded: true,
        output_asset: 'as_outline',
        steps: [
          { index: 0, status: 'completed', detail: 'Brief and target format present.', tokens: 0, cost: 0, started: '14:20:03', finished: '14:20:03', duration: '0.3s' },
          { index: 1, status: 'completed', detail: 'Drafted a six-part outline with a hook per part and a suggested shooting order.', tokens: 6940, cost: 0.112, started: '14:20:12', finished: '14:22:05', duration: '1m 53s', approved_by: 'Avery Kim at 14:20' },
          { index: 2, status: 'completed', detail: 'Score 0.86. Flagged one gap: no troubleshooting section for a starter that will not rise.', tokens: 0, cost: 0, started: '14:22:05', finished: '14:22:06', duration: '0.8s' }
        ] },
      { id: 'r_1044', title: 'Season Two — hook variants', project_id: 'p_kc2',
        workflow: 'project_planning', version: 1, status: 'pending',
        started: 'Today, 09:19', finished: null, tokens: 0, cost: 0.000, by: 'u_avery', seeded: true,
        queue_note: 'Queued behind one other run in this workspace.',
        steps: [
          { index: 0, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null },
          { index: 1, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null },
          { index: 2, status: 'pending', detail: null, tokens: null, cost: null, started: null, finished: null, duration: null }
        ] }
    ],

    spend: [
      { when: '21 Aug 09:12', surface: 'Project planning', run: 'r_1041', provider: 'Anthropic', model: 'claude-sonnet-4-5', tokens: 3180, cost: 0.052, kind: 'existing' },
      { when: '20 Aug 16:40', surface: 'Trailer captions', run: null, provider: 'Anthropic', model: 'claude-sonnet-4-5', tokens: 12400, cost: 0.186, kind: 'planned' },
      { when: '20 Aug 11:47', surface: 'Project planning', run: 'r_1038', provider: 'Anthropic', model: 'claude-sonnet-4-5', tokens: 7420, cost: 0.121, kind: 'existing' },
      { when: '19 Aug 14:02', surface: 'Season key art', run: null, provider: 'OpenAI', model: 'gpt-image-1', tokens: 0, cost: 42.800, kind: 'planned' },
      { when: '18 Aug 16:02', surface: 'Project planning', run: 'r_1037', provider: 'OpenAI', model: 'gpt-4.1-mini', tokens: 5110, cost: 0.021, kind: 'existing' },
      { when: '16 Aug 09:12', surface: 'Trailer script', run: null, provider: 'Anthropic', model: 'claude-sonnet-4-5', tokens: 18600, cost: 0.279, kind: 'planned' },
      { when: '14 Aug 10:25', surface: 'Project planning', run: 'r_1036', provider: 'Anthropic', model: 'claude-sonnet-4-5', tokens: 9260, cost: 0.148, kind: 'existing' },
      { when: '10 Aug 14:22', surface: 'Project planning', run: 'r_1035', provider: 'Anthropic', model: 'claude-sonnet-4-5', tokens: 6940, cost: 0.112, kind: 'existing' }
    ],

    activity: [
      { when: '2 hours ago', who: 'u_diego', what: 'uploaded', target: 'Season Two — Trailer', detail: 'Version 4 — reworked the flip at 00:41.', link: '#/review/as_trailer', kind: 'version' },
      { when: '2 hours ago', who: 'u_diego', what: 'left a note on', target: 'Season Two — Trailer', detail: '“The flip lands two frames early…”', link: '#/review/as_trailer', kind: 'comment' },
      { when: '3 hours ago', who: 'u_priya', what: 'left a note on', target: 'Six Techniques — carousel', detail: '“Slide 4 is the only one with a hand in it.”', link: '#/review/as_carousel', kind: 'comment' },
      { when: '4 hours ago', who: 'u_diego', what: 'sent for review', target: 'The Rise — vertical teaser', detail: 'Reviewer: Noor Haddad.', link: '#/review/as_rise', kind: 'review' },
      { when: 'Today, 09:19', who: 'u_avery', what: 'started', target: 'Season Two — hook variants', detail: 'Queued behind one other run.', link: '#/runs/r_1044', kind: 'run' },
      { when: 'Today, 09:12', who: 'u_avery', what: 'approved a step in', target: 'Pantry — running order', detail: 'Planning agent — one step only.', link: '#/runs/r_1041', kind: 'approval' },
      { when: 'Today, 09:04', who: 'u_avery', what: 'started', target: 'Season Two — episode plan', detail: 'Waiting for your approval at the planning step.', link: '#/runs/r_1042', kind: 'run' },
      { when: 'Yesterday, 17:33', who: null, what: 'stopped', target: 'Cast Iron — explainer plan', detail: 'Retry ceiling reached across two providers.', link: '#/runs/r_1039', kind: 'failure' },
      { when: '20 Aug, 16:40', who: 'u_noor', what: 'approved', target: 'Trailer captions', detail: 'Version 2.', link: '#/review/as_caps', kind: 'approval' },
      { when: '20 Aug, 10:04', who: 'u_avery', what: 'approved', target: 'Episode title cards', detail: 'Version 3.', link: '#/review/as_titles', kind: 'approval' },
      { when: '19 Aug, 14:22', who: 'u_avery', what: 'approved', target: 'Season key art', detail: 'Version 2.', link: '#/review/as_keyart', kind: 'approval' },
      { when: '18 Aug, 11:02', who: 'u_noor', what: 'invited', target: 'Priya Raman', detail: 'Role: Member.', link: '#/settings/members', kind: 'member' }
    ],

    /* A cost ESTIMATE, never a guarantee. Ranges, always. */
    estimate: { low: 0.04, high: 0.14, basis: 'the last 5 planning runs in this workspace', tokens_low: 3200, tokens_high: 9500 }
  };

  /* --------------------------------------------------------------- scenarios
     Prototype-only. Reaches every governed, empty, loading and permission
     state without inventing a product control that would not exist. Each one
     changes the fake SERVER payload; none changes client logic. */
  var SCENARIOS = {
    normal: { label: 'Normal' },
    firstuse: { label: 'First use', empty: true },
    loading: { label: 'Loading', loading: true },
    budget: { label: 'Budget exceeded', budget: { spent_usd: 2012.40 } },
    breaker: { label: 'Breaker open', budget: { breaker_open: true, breaker_reason: 'Six consecutive provider failures in ten minutes. AI calls are paused for this workspace.' } },
    member: { label: 'Signed in as Diego (Editor)',
      user: { id: 'u_diego', name: 'Diego Salas', email: 'diego@averykim.studio', initials: 'DS', role: 'Member' },
      permissions: { role: 'member', can_start_run: true, can_approve: false, can_manage_budget: false, can_manage_members: false,
        denied_reason: 'Your role in this workspace is Member. Approving a step, changing the budget and managing people are Owner and Admin actions.' } },
    ratelimit: { label: 'Rate limited', rateLimited: true },
    offline: { label: 'Service unavailable', offline: true }
  };

  /* ================================================================= state */
  var state = {
    scenario: 'normal',
    runs: JSON.parse(JSON.stringify(DATA.runs)),
    assets: JSON.parse(JSON.stringify(PO.ASSETS)),
    timers: [], simTimers: [], lastFocus: null, nextRunId: 1045,
    route: null, prevRoute: null,
    dismissed: {}
  };

  function server() {
    var s = SCENARIOS[state.scenario] || {};
    return {
      user: Object.assign({}, DATA.user, s.user || {}),
      permissions: Object.assign({}, DATA.permissions, s.permissions || {}),
      budget: Object.assign({}, DATA.budget, s.budget || {}),
      rateLimited: !!s.rateLimited,
      offline: !!s.offline,
      empty: !!s.empty,
      loading: !!s.loading
    };
  }
  function budgetView() {
    var b = server().budget;
    var remaining = b.limit_usd - b.spent_usd;
    return {
      limit: b.limit_usd, spent: b.spent_usd,
      remaining: remaining > 0 ? remaining : 0,
      over: remaining <= 0,
      pct: Math.min(100, Math.round((b.spent_usd / b.limit_usd) * 100)),
      breaker_open: b.breaker_open, breaker_reason: b.breaker_reason, period: b.period_label
    };
  }
  /* Whether a run may START. Read from the payload; never derived here. */
  function startGate() {
    var s = server(), b = budgetView();
    if (s.offline) return { ok: false, why: 'offline' };
    if (!s.permissions.can_start_run) return { ok: false, why: 'permission', reason: s.permissions.denied_reason };
    if (b.breaker_open) return { ok: false, why: 'breaker', reason: b.breaker_reason };
    if (b.over) return { ok: false, why: 'budget' };
    if (s.rateLimited) return { ok: false, why: 'ratelimit' };
    return { ok: true };
  }
  function projects() { return server().empty ? [] : DATA.projects; }
  function runs() { return server().empty ? [] : state.runs; }
  function assets() { return server().empty ? [] : state.assets; }

  var projectById = function (id) { return DATA.projects.filter(function (p) { return p.id === id; })[0]; };
  var runById = function (id) { return state.runs.filter(function (r) { return r.id === id; })[0]; };
  var assetById = function (id) { return state.assets.filter(function (a) { return a.id === id; })[0]; };
  var runsForProject = function (id) { return runs().filter(function (r) { return r.project_id === id; }); };
  var stepDef = function (i) { return WORKFLOW.steps[i]; };
  var person = function (id) {
    var m = DATA.members.filter(function (x) { return x.id === id; })[0];
    return m || { id: id, name: 'Someone', initials: '?', craft: '' };
  };

  var RUN_LABEL = { pending: 'Queued', running: 'Running', awaiting_approval: 'Needs approval', completed: 'Finished', failed: 'Stopped' };
  var RUN_TONE = { pending: 'neutral', running: 'info', awaiting_approval: 'warn', completed: 'ok', failed: 'bad' };
  var PROJECT_LABEL = { idea: 'Idea', planning: 'Planning', generation: 'In production', review: 'In review', editing: 'Editing', approval: 'Approval', publishing: 'Publishing', analytics: 'Analytics', archive: 'Archived' };
  var ASSET_STATE = {
    approved: { label: 'Approved', tone: 'ok', ic: 'check-circle' },
    review: { label: 'In review', tone: 'warn', ic: 'eye' },
    changes: { label: 'Changes requested', tone: 'bad', ic: 'message-square' },
    draft: { label: 'Draft', tone: 'neutral', ic: 'pencil' },
    queued: { label: 'Queued', tone: 'neutral', ic: 'clock' },
    blocked: { label: 'Blocked', tone: 'bad', ic: 'ban' }
  };

  function attentionItems() {
    var out = [], me = server();
    runs().forEach(function (r) {
      if (r.status === 'awaiting_approval') out.push({ kind: 'approval', run: r, title: r.title,
        why: me.permissions.can_approve ? 'One step is waiting for your approval' : 'One step is waiting to be approved',
        act: 'Review the step', href: '#/runs/' + r.id });
      if (r.status === 'failed') out.push({ kind: 'failure', run: r, title: r.title, why: 'Stopped at the planning step — recoverable', act: 'Understand and resume', href: '#/runs/' + r.id });
    });
    assets().forEach(function (a) {
      var open = (a.comments || []).filter(function (c) { return c.open; }).length;
      if (a.state === 'review') out.push({ kind: 'review', asset: a, title: a.name, why: 'Waiting on you for a decision', act: 'Open the review', href: '#/review/' + a.id });
      else if (a.state === 'changes' && open) out.push({ kind: 'changes', asset: a, title: a.name, why: plural(open, 'open note') + ' to resolve', act: 'Open the review', href: '#/review/' + a.id });
    });
    return out;
  }

  /* ============================================================== overlays */
  var openPopover = null;

  function positionPopover(pop, trigger) {
    var r = trigger.getBoundingClientRect();
    pop.hidden = false;
    pop.style.visibility = 'hidden';
    var pw = pop.offsetWidth, ph = pop.offsetHeight;
    var left = r.left, top = r.bottom + 8;
    if (trigger.dataset.popAlign === 'end') left = r.right - pw;
    if (trigger.dataset.popAlign === 'up') top = r.top - ph - 8;
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - ph - 8));
    pop.style.left = Math.round(left) + 'px';
    pop.style.top = Math.round(top) + 'px';
    pop.style.visibility = '';
  }
  function closePopover(restoreFocus) {
    if (!openPopover) return;
    var pop = document.getElementById(openPopover.pop);
    var trg = document.getElementById(openPopover.trigger);
    if (pop) { pop.hidden = true; pop.innerHTML = ''; }
    if (trg) { trg.setAttribute('aria-expanded', 'false'); if (restoreFocus) trg.focus(); }
    openPopover = null;
  }
  function showPopover(popId, triggerId, html) {
    var pop = document.getElementById(popId), trg = document.getElementById(triggerId);
    if (!pop || !trg) return;
    if (openPopover && openPopover.pop === popId) { closePopover(true); return; }
    closePopover(false);
    pop.innerHTML = html;
    openPopover = { pop: popId, trigger: triggerId };
    trg.setAttribute('aria-expanded', 'true');
    positionPopover(pop, trg);
    var first = pop.querySelector('button, [href], input, select');
    if (first) first.focus();
  }

  /* A closed <dialog> must occupy no space. `.drawer`/`.navdrawer` set
     `display:flex` for their open layout, and an author rule beats the user
     agent's `dialog:not([open]) { display:none }` however specific it is — so
     without the author-level rule in styles.css every panel was laid out below
     the fold on every screen. This is the JS half: the stack. */
  var dialogStack = [];

  function openDialog(id, html, opts) {
    opts = opts || {};
    var dlg = document.getElementById(id);
    if (!dlg) return;
    if (!dialogStack.length) state.lastFocus = document.activeElement;
    dlg.innerHTML = html;
    if (!dlg.open) dlg.showModal();

    var already = dialogStack.indexOf(id);
    if (already !== -1) dialogStack.splice(already, 1);
    dialogStack.push(id);

    var focusSel = opts.focus || '[data-autofocus]';
    var target = dlg.querySelector(focusSel) || dlg.querySelector('button, [href], input, select, textarea');
    if (target) target.focus();

    dlg.addEventListener('cancel', function onCancel(e) {
      dlg.removeEventListener('cancel', onCancel);
      e.preventDefault();
      closeDialog(id);
    });
    dlg.addEventListener('click', function onClick(e) {
      if (e.target === dlg) closeDialog(id);
    });
    dlg.addEventListener('close', function onClose() {
      dlg.removeEventListener('close', onClose);
      /* The close event is queued. If the same dialog was re-opened before it
         ran — close then open in one task — this is a stale event and must not
         empty the panel now on screen. */
      if (dlg.open) return;
      var at = dialogStack.indexOf(id);
      if (at !== -1) dialogStack.splice(at, 1);
      dlg.innerHTML = '';
      if (dialogStack.length) return;
      if (state.lastFocus && document.contains(state.lastFocus)) state.lastFocus.focus();
      else { var m = document.getElementById('main-content'); if (m) m.focus(); }
    });
  }
  /* The stack is corrected synchronously, because `close` is queued and an
     overlay opening in the same task as another closes would otherwise find a
     dialog on top of the stack that has already gone. */
  function closeDialog(id) {
    var dlg = document.getElementById(id);
    var at = dialogStack.indexOf(id);
    if (at !== -1) dialogStack.splice(at, 1);
    if (dlg && dlg.open) dlg.close();
    /* Emptied on the way out. A closed dialog is inert, so stale markup does
       no harm on screen — but it keeps stale ids and stale `data-act`
       attributes in the document, and the next thing to search the DOM finds
       them. Overlays own their content only while they are open. */
    if (dlg) dlg.innerHTML = '';
  }
  function closeAllDialogs() { dialogStack.slice().reverse().forEach(closeDialog); }

  /* ---------------------------------------------------------------- toasts */
  function toast(message, kind) {
    /* showModal() puts a dialog in the top layer, which no z-index can beat.
       A toast raised while an overlay is open therefore has to be raised
       INSIDE it, or the user simply never sees it. */
    var host = dialogStack.length
      ? document.getElementById(dialogStack[dialogStack.length - 1])
      : document.getElementById('toasts');
    if (!host) return;
    if (dialogStack.length) {
      var inner = host.querySelector('.toasts--inline');
      if (!inner) {
        inner = document.createElement('div');
        inner.className = 'toasts toasts--inline';
        inner.setAttribute('role', 'status');
        inner.setAttribute('aria-live', 'polite');
        host.appendChild(inner);
      }
      host = inner;
    }
    var el = document.createElement('div');
    el.className = 'toast toast--' + (kind || 'info');
    el.innerHTML = icon(kind === 'ok' ? 'check-circle' : kind === 'bad' ? 'alert-circle' : 'info', 'icon') +
      '<span>' + esc(message) + '</span>';
    host.appendChild(el);
    /* Deliberately NOT in state.timers: render() clears that array, and a
       toast fired just before a navigation would then never dismiss itself.
       Four permanent toasts stacked over the screen was the old bug. */
    setTimeout(function () {
      el.classList.add('is-out');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 220);
    }, 4600);
  }

  /* ================================================================ router */

  var NAV = [
    { group: 'make', route: 'dashboard', href: '#/dashboard', label: 'Home', icon: 'home' },
    { group: 'make', route: 'projects', href: '#/projects', label: 'Projects', icon: 'layers' },
    { group: 'make', route: 'studio', href: '#/studio', label: 'Studio', icon: 'scissors' },
    { group: 'make', route: 'library', href: '#/library', label: 'Library', icon: 'grid' },
    { group: 'make', route: 'runs', href: '#/runs', label: 'Production', icon: 'activity' },
    { group: 'aside', route: 'assistant', href: '#/assistant', label: 'Assistant', icon: 'message-circle' },
    { group: 'aside', route: 'activity', href: '#/activity', label: 'Activity', icon: 'history' },
    { group: 'aside', route: 'spend', href: '#/spend', label: 'AI spend', icon: 'wallet' },
    { group: 'aside', route: 'settings', href: '#/settings/profile', label: 'Settings', icon: 'sliders' }
  ];

  /* Route table. `tpl` picks one of three page templates and nothing else:
     cockpit (full-width working surfaces), workbench (a split view with an
     inspector), focus (a centred column for consequential forms). */
  var ROUTES = {
    dashboard: { tpl: 'cockpit', title: 'Home', nav: 'dashboard' },
    plan: { tpl: 'focus', title: 'Creation plan', nav: 'dashboard', back: '#/dashboard' },
    projects: { tpl: 'workbench', title: 'Projects', nav: 'projects' },
    project: { tpl: 'workbench', title: 'Project', nav: 'projects', back: '#/projects' },
    studio: { tpl: 'cockpit', title: 'Studio', nav: 'studio' },
    library: { tpl: 'cockpit', title: 'Library', nav: 'library' },
    runs: { tpl: 'workbench', title: 'Production', nav: 'runs' },
    run: { tpl: 'workbench', title: 'Run', nav: 'runs', back: '#/runs' },
    review: { tpl: 'workbench', title: 'Review', nav: 'library', back: '#/library' },
    activity: { tpl: 'workbench', title: 'Activity', nav: 'activity' },
    assistant: { tpl: 'workbench', title: 'Assistant', nav: 'assistant' },
    spend: { tpl: 'cockpit', title: 'AI spend', nav: 'spend' },
    settings: { tpl: 'focus', title: 'Settings', nav: 'settings' },
    signin: { tpl: 'focus', title: 'Sign in', chrome: false },
    join: { tpl: 'focus', title: 'Join the workspace', chrome: false },
    welcome: { tpl: 'focus', title: 'Welcome', chrome: false },
    spec: { tpl: 'cockpit', title: 'Components', nav: null },
    notfound: { tpl: 'focus', title: 'Not found', nav: null }
  };

  /* A hash that is not a route is an in-page fragment — `#main-content` from
     the skip link is the one every prototype gets wrong. Treating it as a
     route sent the primary keyboard affordance to Not Found and destroyed the
     screen the user was standing on. Anything without a leading slash is
     therefore left entirely alone. */
  function isRouteHash(h) { return !h || h === '#' || h.charAt(1) === '/'; }

  /* Some hosts will not let a document write its own fragment — a `data:`
     document is the common one. Hash routing is still the addressing scheme;
     this is only a fallback so that a page which cannot change its own URL
     still navigates. Where it engages, the address bar stops tracking the
     route and browser back/forward stop applying to it, which is the honest
     cost and is why it is a fallback rather than the mechanism. */
  var forcedHash = null;
  function currentHash() { return forcedHash || location.hash || '#/dashboard'; }

  function parseRoute() {
    if (!isRouteHash(currentHash())) return state.route || { name: 'dashboard', q: {} };
    var h = (currentHash() || '#/dashboard').replace(/^#\/?/, '');
    var parts = h.split('?')[0].split('/').filter(Boolean);
    var q = {};
    var qs = h.split('?')[1];
    if (qs) qs.split('&').forEach(function (kv) {
      var p = kv.split('='); q[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || '');
    });
    if (!parts.length) return { name: 'dashboard', q: q };
    var head = parts[0];
    if (head === 'projects') return parts[1] ? { name: 'project', id: parts[1], tab: parts[2] || 'overview', q: q } : { name: 'projects', q: q };
    if (head === 'runs') return parts[1] ? { name: 'run', id: parts[1], q: q } : { name: 'runs', q: q };
    if (head === 'studio') return { name: 'studio', id: parts[1] || null, q: q };
    if (head === 'review') return { name: 'review', id: parts[1] || null, q: q };
    if (head === 'library') return { name: 'library', tab: parts[1] || 'assets', q: q };
    if (head === 'settings') return { name: 'settings', tab: parts[1] || 'profile', q: q };
    if (ROUTES[head]) return { name: head, q: q };
    return { name: 'notfound', id: head, q: q };
  }

  function clearTimers() {
    state.timers.forEach(clearTimeout);
    state.timers = [];
  }
  function go(hash) {
    if (currentHash() === hash) { render(); return; }
    forcedHash = null;
    try { location.hash = hash; } catch (e) { /* fallback below */ }
    if (location.hash !== hash) { forcedHash = hash; render(); }
  }

  function renderRail() {
    var host = document.getElementById('rail-nav');
    if (!host) return;
    var active = (ROUTES[state.route.name] || {}).nav;
    var groups = [['make', null], ['aside', 'Workspace']];
    host.innerHTML = groups.map(function (g) {
      var items = NAV.filter(function (n) { return n.group === g[0]; });
      return (g[1] ? '<li class="rail__label" aria-hidden="true">' + esc(g[1]) + '</li>' : '') +
        items.map(function (n) {
          var on = n.route === active;
          var count = n.route === 'runs' ? attentionItems().filter(function (i) { return i.kind === 'approval' || i.kind === 'failure'; }).length : 0;
          return '<li><a class="navitem' + (on ? ' is-active' : '') + '" href="' + n.href + '"' +
            (on ? ' aria-current="page"' : '') + '>' +
            '<span class="navitem__mark" aria-hidden="true"></span>' +
            icon(n.icon, 'icon icon--lg') + '<span class="navitem__label">' + esc(n.label) + '</span>' +
            (count ? '<span class="navitem__count">' + count + '<span class="u-sr-only"> need attention</span></span>' : '') +
            '</a></li>';
        }).join('');
    }).join('');
  }

  function render() {
    clearTimers();
    closePopover(false);
    var route = parseRoute();
    state.prevRoute = state.route;
    state.route = route;
    var def = ROUTES[route.name] || ROUTES.notfound;

    document.body.dataset.view = route.name;
    document.body.dataset.tpl = def.tpl;
    document.body.dataset.chrome = def.chrome === false ? 'off' : 'on';

    var host = document.getElementById('screen');
    if (!host) return;

    var s = server();
    var view = PO.views[route.name] || PO.views.notfound;
    var html;
    if (def.chrome !== false && s.loading && route.name !== 'spec') html = PO.ui.skeletonFor(route.name);
    else html = view(route);
    host.innerHTML = html;

    /* One route transition, 180ms, and nothing else moves. */
    host.classList.remove('is-entering');
    void host.offsetWidth;
    host.classList.add('is-entering');

    renderRail();
    renderTopbar(def, route);
    renderIdentity();
    renderNotifBadge();
    if (PO.views.after && PO.views.after[route.name]) PO.views.after[route.name](route);
    window.scrollTo(0, 0);
    var main = document.getElementById('main-content');
    if (main) main.scrollTop = 0;
  }

  function renderTopbar(def, route) {
    var t = document.getElementById('topbar-title');
    if (t) {
      var label = def.title;
      if (route.name === 'project') { var p = projectById(route.id); label = p ? p.name : 'Project'; }
      if (route.name === 'run') { var r = runById(route.id); label = r ? r.title : 'Run'; }
      if (route.name === 'review') { var a = assetById(route.id); label = a ? a.name : 'Review'; }
      t.textContent = label;
    }
    var back = document.getElementById('topbar-back');
    if (back) {
      var href = def.back;
      if (route.name === 'review') { var av = assetById(route.id); href = av ? '#/library' : '#/library'; }
      if (href) { back.hidden = false; back.setAttribute('href', href); }
      else back.hidden = true;
    }
  }

  /* The rail's identity is payload-driven too. Leaving it as static markup is
     how a prototype ends up saying "Owner" on the very screen whose purpose is
     to show what a Member cannot do. */
  function renderIdentity() {
    var s = server();
    var role = s.permissions.role;
    var set = function (id, text) { var e = document.getElementById(id); if (e) e.textContent = text; };
    set('ws-name', DATA.workspace.name);
    set('ws-role', role.charAt(0).toUpperCase() + role.slice(1));
    set('user-name', s.user.name);
    set('user-role', s.user.email);
    /* Keep the chrome's own control in step with the payload it selects, so
       the bar can never disagree with the screen underneath it. */
    var sel = document.getElementById('scenario');
    if (sel && sel.value !== state.scenario) sel.value = state.scenario;
    var av = document.querySelector('#user-trigger .avatar');
    if (av) av.textContent = s.user.initials;
  }

  function renderNotifBadge() {
    var n = attentionItems().length;
    var badge = document.getElementById('notif-count');
    var label = document.getElementById('notif-label');
    if (badge) { badge.textContent = String(n); badge.hidden = n === 0; }
    if (label) label.textContent = n ? 'Notifications, ' + plural(n, 'item') + ' need attention' : 'Notifications, nothing needs attention';
  }

  /** Re-render in place, then put focus back where the user left it. */
  function refresh(refocusSelector) {
    render();
    if (!refocusSelector) return;
    var el = document.querySelector(refocusSelector);
    if (el) el.focus();
  }

  /* ==================================================== shared components */

  function ambientCost(compact) {
    var b = budgetView();
    var tone = b.breaker_open ? 'bad' : b.over ? 'bad' : b.pct > 80 ? 'warn' : 'ok';
    return '<a class="ambient ambient--' + tone + (compact ? ' ambient--compact' : '') + '" href="#/spend">' +
      '<span class="ambient__bar" aria-hidden="true"><span class="ambient__fill" style="width:' + b.pct + '%"></span></span>' +
      '<span class="ambient__text">' + money(b.spent) + ' <span class="t-muted">of ' + money(b.limit) + '</span></span>' +
      '</a>';
  }

  function badge(tone, label, ic) {
    return '<span class="badge badge--' + tone + '">' + (ic ? icon(ic, 'icon icon--sm') : '') + esc(label) + '</span>';
  }
  function runBadge(status) { return badge(RUN_TONE[status] || 'neutral', RUN_LABEL[status] || status); }
  function assetBadge(st) {
    var d = ASSET_STATE[st] || ASSET_STATE.draft;
    return badge(d.tone, d.label, d.ic);
  }
  function projectBadge(status) {
    var tone = status === 'archive' ? 'neutral' : status === 'generation' ? 'info' : status === 'review' ? 'warn' : 'neutral';
    return badge(tone, PROJECT_LABEL[status] || status);
  }
  function avatar(id, size) {
    var p = person(id);
    return '<span class="avatar' + (size ? ' avatar--' + size : '') + '" title="' + esc(p.name) + '">' + esc(p.initials) + '</span>';
  }
  function faces(ids, max) {
    max = max || 4;
    var shown = ids.slice(0, max);
    return '<span class="faces">' + shown.map(function (id) { return avatar(id, 'sm'); }).join('') +
      (ids.length > max ? '<span class="avatar avatar--sm avatar--more">+' + (ids.length - max) + '</span>' : '') +
      '<span class="u-sr-only">' + ids.map(function (i) { return person(i).name; }).join(', ') + '</span></span>';
  }

  /** A piece of media in its frame. `a` is an asset; `opts.aspect` overrides. */
  function frame(a, opts) {
    opts = opts || {};
    var aspect = opts.aspect || (a && a.doc === 'carousel' ? '1x1' : (a && a.doc ? '4x5' : (a && a.aspect) || '16x9'));
    var cls = 'frame frame--' + aspect + (opts.cls ? ' ' + opts.cls : '');
    var art = PO.art.of(a, { aspect: aspect, detail: opts.detail, lockup: opts.lockup, seat: opts.seat });
    var over = '';
    if (opts.duration) over += '<span class="frame__chip">' + esc(opts.duration) + '</span>';
    if (opts.version) over += '<span class="frame__ver">v' + a.version + '</span>';
    if (opts.n > 1) over += '<span class="frame__n">×' + opts.n + '</span>';
    if (opts.gate) over += '<span class="frame__gate" title="Needs approval before it runs">' + icon('shield-check', 'icon icon--sm') + '</span>';
    if (opts.state && a) {
      var d = ASSET_STATE[a.state];
      if (d && (a.state === 'review' || a.state === 'changes')) over += '<span class="frame__rule frame__rule--' + d.tone + '"></span>';
      if (d && a.state === 'approved') over += '<span class="frame__stamp">' + icon('check', 'icon icon--sm') + 'Approved</span>';
    }
    if (opts.stack) over = '<span class="frame__stack" aria-hidden="true"></span>' + over;
    return '<span class="' + cls + '">' + art + over + '</span>';
  }

  function bandHead(label, link, linkLabel) {
    return '<div class="band__head"><h2 class="eyebrow">' + esc(label) + '</h2>' +
      (link ? '<a class="band__link" href="' + link + '">' + esc(linkLabel || 'See all') + icon('chevron-right', 'icon icon--sm') + '</a>' : '') +
      '</div>';
  }

  function notice(kind, ic, title, text, actions) {
    return '<div class="notice notice--' + kind + '" role="' + (kind === 'bad' ? 'alert' : 'status') + '">' +
      '<span class="notice__ic">' + icon(ic, 'icon icon--lg') + '</span>' +
      '<div class="notice__body"><p class="notice__title">' + esc(title) + '</p>' +
      (text ? '<p class="notice__text">' + text + '</p>' : '') + '</div>' +
      (actions ? '<div class="notice__act">' + actions + '</div>' : '') + '</div>';
  }

  /** The governed conditions that must interrupt whatever the user came for. */
  function governedNotices(context) {
    var s = server(), b = budgetView(), out = '';
    if (s.offline) {
      out += notice('bad', 'alert-triangle', 'ProjectOne cannot reach its services right now.',
        'Nothing you have done is lost. Starting production and approving steps are unavailable until the connection is back; everything already saved is still here.',
        '<button type="button" class="btn btn--secondary btn--sm" data-act="retry">Try again</button>');
    }
    if (b.breaker_open) {
      out += notice('bad', 'ban', 'AI work is paused for this workspace.',
        esc(b.breaker_reason) + ' Nothing new will start until this is cleared. Work already saved is unaffected.',
        '<a class="btn btn--secondary btn--sm" href="#/spend">Open AI spend</a>');
    } else if (b.over) {
      out += notice('warn', 'wallet', 'This workspace is at its monthly AI ceiling.',
        'You have used <strong>' + money(b.spent) + '</strong> of the <strong>' + money(b.limit) + '</strong> set for ' + esc(b.period) +
        '. A run already in flight is allowed to finish rather than being cut off mid-draft, which is why the figure can land just past the limit. Nothing new will start.',
        '<a class="btn btn--secondary btn--sm" href="#/settings/billing">Raise the ceiling</a>');
    }
    if (s.rateLimited && context !== 'quiet') {
      out += notice('warn', 'clock', 'Too many requests in a short window.',
        'This workspace has hit its rate limit. It clears on its own within a minute — nothing is broken and nothing is lost.');
    }
    if (!s.permissions.can_start_run && s.permissions.denied_reason && context === 'start') {
      out += notice('info', 'lock', 'You can look, but you cannot start this.', esc(s.permissions.denied_reason));
    }
    return out;
  }

  /* `as` lets a screen whose whole body is an empty state supply the page's
     one h1 from it, rather than leaving the document with no heading at all. */
  function empty(ic, title, text, action, as) {
    var tag = as || 'p';
    return '<div class="empty">' + icon(ic, 'icon icon--xl') +
      '<' + tag + ' class="empty__title t-h2">' + esc(title) + '</' + tag + '>' +
      '<p class="empty__text t-sm t-muted">' + text + '</p>' +
      (action ? '<div class="empty__act">' + action + '</div>' : '') + '</div>';
  }

  function skel(w, h, cls) {
    return '<span class="skel' + (cls ? ' ' + cls : '') + '" style="width:' + w + ';height:' + h + '"></span>';
  }

  /* Exported for screens.js. Everything a screen needs and nothing more. */
  PO.ui = {
    $: $, $$: $$, esc: esc, icon: icon, money: money, money3: money3, num: num, plural: plural, anno: anno,
    DATA: DATA, WORKFLOW: WORKFLOW, SCENARIOS: SCENARIOS, state: state, NAV: NAV, ROUTES: ROUTES,
    server: server, budgetView: budgetView, startGate: startGate,
    projects: projects, runs: runs, assets: assets,
    projectById: projectById, runById: runById, assetById: assetById, runsForProject: runsForProject,
    stepDef: stepDef, person: person, attentionItems: attentionItems,
    RUN_LABEL: RUN_LABEL, RUN_TONE: RUN_TONE, PROJECT_LABEL: PROJECT_LABEL, ASSET_STATE: ASSET_STATE,
    badge: badge, runBadge: runBadge, assetBadge: assetBadge, projectBadge: projectBadge,
    avatar: avatar, faces: faces, frame: frame, bandHead: bandHead, notice: notice,
    governedNotices: governedNotices, empty: empty, skel: skel, ambientCost: ambientCost,
    openDialog: openDialog, closeDialog: closeDialog, closeAllDialogs: closeAllDialogs,
    showPopover: showPopover, closePopover: closePopover,
    toast: toast, go: go, render: render, refresh: refresh, parseRoute: parseRoute
  };

  /* ------------------------------------------------------- global listeners */

  function boot() {
    /* Delegated click. One listener for the whole application, so a screen can
       be re-rendered wholesale without ever rebinding anything. */
    document.addEventListener('click', function (e) {
      var t = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
      if (!t) {
        if (openPopover && !e.target.closest('.popover') && !e.target.closest('[aria-haspopup]')) closePopover(false);
        return;
      }
      var act = t.dataset.act;
      var fn = PO.actions[act];
      if (!fn) return;
      e.preventDefault();
      fn(t.dataset.arg, t, e);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && openPopover) { closePopover(true); return; }
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (PO.actions['palette']) PO.actions['palette']();
      }
    });

    /* The trigger is sticky and the panel is absolutely positioned, so a
       scroll separates them. Closing is the honest response — repositioning a
       menu the user is scrolling past is worse than dismissing it. */
    var onMove = function () { if (openPopover) closePopover(false); };
    window.addEventListener('resize', onMove);
    window.addEventListener('scroll', onMove, true);

    window.addEventListener('hashchange', function () {
      forcedHash = null;
      if (!isRouteHash(location.hash)) return;
      closeAllDialogs();
      render();
    });

    if (PO.bootExtras) PO.bootExtras();
    render();
  }

  PO.boot = boot;
  PO.actions = PO.actions || {};
  PO.core = { render: render, go: go, refresh: refresh, renderRail: renderRail,
              renderNotifBadge: renderNotifBadge, renderIdentity: renderIdentity };
})();

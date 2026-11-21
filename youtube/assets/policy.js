/* MiniMedia TV page policy. Local asset; no remote executable code. */
(function () {
    'use strict';
    function createPolicy(onPlayer) {
        var DROP = {}, stats = {ads: 0, shorts: 0, guides: 0, homeRequests: 0};
        var adRenderers = ['adSlotRenderer', 'displayAdRenderer', 'promotedVideoRenderer',
            'promotedSparklesWebRenderer', 'promotedSparklesTextSearchRenderer',
            'mastheadAdRenderer', 'tvMastheadAdRenderer', 'inFeedAdLayoutRenderer'];
        var shortRenderers = ['reelShelfRenderer', 'reelItemRenderer', 'shortsLockupViewModel',
            'shortsShelfRenderer', 'shortsLockupViewModelV2'];
        var hiddenBrowse = ['FEwhat_to_watch', 'FEtrending', 'FEexplore', 'FEshorts',
            'FEgaming', 'FEmusic', 'FEnews', 'FEsports', 'FEpodcasts'];
        function blocked(value) {
            var i, entry, endpoint, id;
            if (!value || typeof value !== 'object') return false;
            for (i = 0; i < adRenderers.length; i++) if (value[adRenderers[i]]) { stats.ads++; return true; }
            for (i = 0; i < shortRenderers.length; i++) if (value[shortRenderers[i]]) { stats.shorts++; return true; }
            entry = value.guideEntryRenderer || value.guideCollapsibleEntryRenderer;
            if (entry) {
                endpoint = entry.navigationEndpoint || entry.endpoint || {};
                id = endpoint.browseEndpoint && endpoint.browseEndpoint.browseId;
                if (hiddenBrowse.indexOf(id) !== -1 || (endpoint.reelWatchEndpoint)) { stats.guides++; return true; }
            }
            return false;
        }
        function visit(value, depth, budget) {
            var i, key, result, output;
            if (!value || typeof value !== 'object' || depth > 80 || budget.count++ > 100000) return value;
            if (blocked(value)) return DROP;
            if (Array.isArray(value)) {
                output = [];
                for (i = 0; i < value.length; i++) {
                    result = visit(value[i], depth + 1, budget);
                    if (result !== DROP) output.push(result);
                }
                value.length = 0;
                for (i = 0; i < output.length; i++) value.push(output[i]);
                return value;
            }
            if (value.videoDetails && value.streamingData && onPlayer) onPlayer(value.videoDetails.videoId);
            for (key in value) if (Object.prototype.hasOwnProperty.call(value, key)) {
                if (key === 'adPlacements' || key === 'playerAds' || key === 'adSlots') {
                    if (value[key] && value[key].length) stats.ads += value[key].length;
                    value[key] = [];
                } else if (key === 'adBreakHeartbeatParams' || key === 'adTrackingParams'
                        || key === 'endscreen' || key === 'endScreenRenderer') {
                    delete value[key];
                } else {
                    result = visit(value[key], depth + 1, budget);
                    if (result === DROP) {
                        // Remove the containing tile wrapper as well as its inner renderer.
                        if ((key === 'content' || key === 'richItemRenderer' || key === 'richSectionRenderer')
                                && (value.trackingParams || Object.keys(value).length <= 2)) return DROP;
                        delete value[key];
                    }
                }
            }
            // The watch-next secondary rail consists of recommendations, not the player.
            if (value.secondaryResults && value.secondaryResults.secondaryResults)
                value.secondaryResults.secondaryResults.results = [];
            return value;
        }
        function clean(value) {
            var result = visit(value, 0, {count: 0});
            return result === DROP ? {} : result;
        }
        function rewriteBody(url, body, parse, stringify) {
            if (!/\/youtubei\/v1\/browse(?:\?|$)/.test(String(url)) || typeof body !== 'string') return body;
            try {
                var request = parse(body);
                if (request && request.browseId === 'FEwhat_to_watch') {
                    request.browseId = 'FEsubscriptions';
                    delete request.params;
                    stats.homeRequests++;
                    return stringify(request);
                }
            } catch (ignored) {}
            return body;
        }
        return {clean: clean, rewriteBody: rewriteBody, stats: stats};
    }
    if (typeof module !== 'undefined' && module.exports) { module.exports = createPolicy; return; }
    if (!/(^|\.)youtube\.com$/.test(location.hostname)) return 'wrong-origin';
    if (window.__miniMediaYT) return 'already-installed';

    var nativeParse = JSON.parse, nativeStringify = JSON.stringify;
    var currentVideo = null, segments = [], lastRequestedVideo = null;
    var nativeFetch = window.fetch && window.fetch.bind(window);
    var policy = createPolicy(function (videoId) {
        if (!videoId || !/^[A-Za-z0-9_-]{11}$/.test(videoId) || currentVideo === videoId) return;
        currentVideo = videoId;
        segments = [];
        if (!nativeFetch || lastRequestedVideo === videoId) return;
        lastRequestedVideo = videoId;
        var expected = videoId;
        // SponsorBlock receives only the public video ID; no account token or cookies.
        nativeFetch('https://sponsor.ajay.app/api/skipSegments?videoID=' + encodeURIComponent(videoId)
            + '&categories=' + encodeURIComponent('["sponsor"]'), {credentials: 'omit'})
            .then(function (response) { return response.status === 200 ? response.text() : '[]'; })
            .then(function (text) {
                if (currentVideo !== expected) return;
                var entries = nativeParse(text);
                if (Array.isArray(entries)) segments = entries.filter(function (entry) {
                    return entry.category === 'sponsor' && Array.isArray(entry.segment)
                        && typeof entry.segment[0] === 'number' && typeof entry.segment[1] === 'number'
                        && isFinite(entry.segment[0]) && isFinite(entry.segment[1])
                        && entry.segment[0] >= 0 && entry.segment[1] > entry.segment[0];
                });
            }).catch(function () {});
    });
    window.__miniMediaYT = {version: 1, stats: policy.stats};
    JSON.parse = function () { return policy.clean(nativeParse.apply(JSON, arguments)); };
    function apiUrl(url) {
        try {
            var parsed = new URL(String(url), location.href);
            return /(^|\.)youtube\.com$/.test(parsed.hostname) && /^\/youtubei\/v1\//.test(parsed.pathname);
        } catch (ignored) { return false; }
    }
    function sanitizeText(text) {
        if (text.length > 8 * 1024 * 1024) return text;
        var prefix = text.indexOf(")]}'") === 0 ? text.slice(0, text.indexOf('\n') + 1) : '';
        try { return prefix + nativeStringify(policy.clean(nativeParse(text.slice(prefix.length)))); }
        catch (ignored) { return text; }
    }
    if (nativeFetch) window.fetch = function (input, init) {
        var url = typeof input === 'string' ? input : input.url;
        if (!apiUrl(url)) return nativeFetch(input, init);
        if (init && typeof init.body === 'string') {
            var replacement = {};
            Object.keys(init).forEach(function (key) { replacement[key] = init[key]; });
            replacement.body = policy.rewriteBody(url, init.body, nativeParse, nativeStringify);
            init = replacement;
        }
        return nativeFetch(input, init).then(function (response) {
            if (!response.ok || !/json/.test(response.headers.get('content-type') || '')) return response;
            return response.clone().text().then(function (text) {
                var headers = new Headers(response.headers);
                headers.delete('content-length'); headers.delete('content-encoding');
                var updated = new Response(sanitizeText(text), {status: response.status,
                    statusText: response.statusText, headers: headers});
                try { Object.defineProperty(updated, 'url', {value: response.url}); } catch (ignored) {}
                return updated;
            }).catch(function () { return response; });
        });
    };
    if (window.XMLHttpRequest) {
        var originalOpen = XMLHttpRequest.prototype.open, originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function (method, url) {
            this.__miniMediaUrl = String(url);
            if (!this.__miniMediaObserver) {
                this.__miniMediaObserver = true;
                this.addEventListener('readystatechange', function () {
                    if (this.readyState !== 4 || !apiUrl(this.__miniMediaUrl)) return;
                    try {
                        if (!this.responseType || this.responseType === 'text') {
                            var text = sanitizeText(this.responseText);
                            Object.defineProperty(this, 'responseText', {configurable: true, get: function () { return text; }});
                            Object.defineProperty(this, 'response', {configurable: true, get: function () { return text; }});
                        } else if (this.responseType === 'json') {
                            var cleaned = policy.clean(this.response);
                            Object.defineProperty(this, 'response', {configurable: true, get: function () { return cleaned; }});
                        }
                    } catch (ignored) {}
                });
            }
            // A reused XHR must not keep the previous response's instance getters.
            try { delete this.response; delete this.responseText; } catch (ignored) {}
            return originalOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function (body) {
            return originalSend.call(this, policy.rewriteBody(this.__miniMediaUrl, body, nativeParse, nativeStringify));
        };
    }

    var style = document.createElement('style');
    style.textContent = 'ytlr-reel-shelf-renderer,ytlr-reel-item-renderer,ytlr-shorts-shelf-renderer,'
        + '[data-content-type="shorts"],a[href*="/shorts/"]{display:none!important;}';
    (document.head || document.documentElement).appendChild(style);
    var hiddenNavigation = /^(Home|Shorts|Explore|Trending|Music|Gaming|News|Sports|Podcasts)$/i;
    function tidyGuide() {
        var guide = document.querySelector('ytlr-guide-renderer,ytlr-guide,#guide');
        if (!guide) return;
        var entries = guide.querySelectorAll('[role="menuitem"],[role="link"],a,ytlr-guide-entry-renderer');
        for (var i = 0; i < entries.length; i++) {
            var label = (entries[i].getAttribute('aria-label') || entries[i].textContent || '').replace(/\s+/g, ' ').trim();
            if (hiddenNavigation.test(label)) entries[i].style.display = 'none';
        }
    }
    var pending = false;
    if (window.MutationObserver) new MutationObserver(function () {
        if (pending) return;
        pending = true;
        setTimeout(function () { pending = false; tidyGuide(); }, 150);
    }).observe(document.documentElement, {childList: true, subtree: true});
    tidyGuide();
    setInterval(function () {
        if (document.hidden || !segments.length) return;
        var video = document.querySelector('video');
        if (!video || video.paused || !isFinite(video.duration)) return;
        for (var i = 0; i < segments.length; i++) {
            var range = segments[i].segment;
            if (video.currentTime >= range[0] && video.currentTime < range[1] - 0.2) {
                video.currentTime = Math.min(range[1], video.duration);
                break;
            }
        }
    }, 500);
    return 'installed-local-policy-v1';
})();

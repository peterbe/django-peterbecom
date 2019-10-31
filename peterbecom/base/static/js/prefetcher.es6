const requestIdleCallback =
  requestIdleCallback ||
  function(cb) {
    const start = Date.now();
    return setTimeout(function() {
      cb({
        didTimeout: false,
        timeRemaining: function() {
          return Math.max(0, 50 - (Date.now() - start));
        }
      });
    }, 1);
  };
requestIdleCallback(() => {
  /**
   * Checks if a feature on `link` is natively supported.
   * Examples of features include `prefetch` and `preload`.
   * @param {string} feature - name of the feature to test
   * @return {Boolean} whether the feature is supported
   */
  function support(feature) {
    const link = document.createElement('link');
    return (link.relList || {}).supports && link.relList.supports(feature);
  }

  /**
   * Fetches a given URL using `<link rel=prefetch>`
   * @param {string} url - the URL to fetch
   * @return {Object} a Promise
   */
  function linkPrefetchStrategy(url) {
    return new Promise((resolve, reject) => {
      const link = document.createElement(`link`);
      link.rel = `prefetch`;
      link.href = url;
      link.onload = resolve;
      link.onerror = reject;
      document.head.appendChild(link);
    });
  }

  /**
   * Fetches a given URL using XMLHttpRequest
   * @param {string} url - the URL to fetch
   * @return {Object} a Promise
   */
  function xhrPrefetchStrategy(url) {
    return new Promise((resolve, reject) => {
      const req = new XMLHttpRequest();

      req.open(`GET`, url, (req.withCredentials = true));

      req.onload = () => {
        req.status === 200 ? resolve() : reject();
      };

      req.send();
    });
  }

  const supportedPrefetchStrategy = support('prefetch')
    ? linkPrefetchStrategy
    : xhrPrefetchStrategy;

  const preFetched = {};

  /**
   * Prefetch a given URL with an optional preferred fetch priority
   * @param {String} url - the URL to fetch
   * @return {Object} a Promise
   */
  function prefetcher(url, conn) {
    if (preFetched[url]) {
      return;
    }

    if ((conn = navigator.connection)) {
      // Don't prefetch if the user is on 2G. or if Save-Data is enabled..
      if ((conn.effectiveType || '').includes('2g') || conn.saveData) return;
    }

    // Wanna do something on catch()?
    return supportedPrefetchStrategy(url).then(() => {
      preFetched[url] = true;
    });
  }

  function onMouseOver(event) {
    const url = new URL(event.target.href, document.location.href);
    prefetchTimer = setTimeout(() => {
      prefetcher(url);
      event.target.removeEventListener('mouseover', onMouseOver);
    }, 200);
  }

  function onMouseOut(event) {
    if (prefetchTimer) {
      clearTimeout(prefetchTimer);
    }
  }
  /**
   * Main function...
   */
  const MAX_PREFETCH = 5;
  const toPrefetch = new Set();
  var prefetchTimer = null;
  Array.from(document.querySelectorAll('a'), link => {
    if (
      link.href &&
      link.rel !== 'nofollow' &&
      toPrefetch.size < MAX_PREFETCH
    ) {
      const url = new window.URL(link.href, document.location.href);
      if (
        url.host === document.location.host &&
        !/\.[a-z0-9]{2,3}$/.test(url.pathname)
      ) {
        link.addEventListener('mouseover', onMouseOver);
        link.addEventListener('mouseout', onMouseOut);
      }
    }
  });
});

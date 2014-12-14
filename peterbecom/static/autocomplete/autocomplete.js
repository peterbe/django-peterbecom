/*!
*
* Copyright (c) 2015, Peter Bengtsson
*
* Permission is hereby granted, free of charge, to any person obtaining a copy
* of this software and associated documentation files (the "Software"), to deal
* in the Software without restriction, including without limitation the rights
* to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
* copies of the Software, and to permit persons to whom the Software is
* furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in
* all copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
* IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
* FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
* LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
* OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
* THE SOFTWARE.
*
*/

/*
 * How to use it
 * -------------
 *
 * Load this file and then call it like this:
 *
 *     Autocomplete(document.getElementById('searchthing'));
 *
 * More to come...
 */

var Autocomplete = (function(window, document, undefined) { /* TODO: can 'undefined' be removed */
  'use strict';

  /* utility function to create DOM elements */
  function createDomElement(tag, options) {
    var e = document.createElement(tag);
    for (var key in options) {
      e[key] = options[key];
    }
    return e;
  }

  /* utility function to attach event handlers to elements */
  function attachHandler(target, type, handler) {
    if (target.addEventListener) {
      target.addEventListener(type, handler, false);
    } else {
      target.attachEvent(type, handler);
    }
  }

  function extend() {
    var key, object, objects, target, val, i, len, slice = [].slice;
    target = arguments[0];
    objects = 2 <= arguments.length ? slice.call(arguments, 1) : [];
    for (i = 0, len = objects.length; i < len; i++) {
      object = objects[i];
      for (key in object) {
        val = object[key];
        target[key] = val;
      }
    }
    return target;
  }

  return function setUp(q, options) {
    options = options || {};
    options = extend({
      url: '/autocomplete',
      key: 'q'
    }, options || {});
    options.url += (options.url.indexOf('?') > -1 ? '&' : '?') + options.key + '=';

    var results_ps = [];
    var selected_pointer = 0;
    q.spellcheck = false;
    q.autocomplete = 'off';
    var r;

    // wrap the input
    var wrapper = createDomElement('span', {className: '_ac-wrap'});
    var hint = createDomElement('input', {
      tabindex: -1,
      spellcheck: false,
      autocomplete: 'off',
      readonly: 'readonly',
      type: 'text',
      className: q.className + ' _ac-hint'
    });

    // The hint is a clone of the original but the original has some
    // requirements of its own.
    q.classList.add('_ac-foreground');
    wrapper.appendChild(hint);
    var clone = q.cloneNode(true);
    wrapper.appendChild(clone);

    r = createDomElement('div', {className: '_ac-results'});
    attachHandler(r, 'mouseover', mouseoverResults);
    wrapper.appendChild(r);

    q.parentElement.insertBefore(wrapper, q);
    q.parentNode.removeChild(q);
    q = clone;

    function escapeRegExp(str) {
      return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&");
    }
    function highlightText(text) {
      var search_terms = terms.map(escapeRegExp);
      var re = new RegExp('\\b(' + search_terms.join('|') + ')', 'gi');
      return text.replace(re, '<b>$1</b>');
    }

    function mouseoverResults(e) {
      if (e.target.tagName === 'P') {
        if (selected_pointer !== +e.target.dataset.i) {
          selected_pointer = +e.target.dataset.i;
          displayResults();
        }
      }
    }

    var results = null;
    var terms;
    function displayResults() {
      var i, len;
      // terms = response.terms;
      // var results = response.results;
      if (results === null) return;
      // console.log('results', results)
      if (results.length) {
        r.style.display = 'block';
        var ps = r.getElementsByTagName('p');
        for (i=ps.length - 1; i >= 0; i--) {
          ps[i].remove();
        }
      } else {
        r.style.display = 'none';
      }
      results_ps = [];
      var p, a;
      // console.log(results);
      var hint_candidate = null;
      var hint_candidates = [];
      if (!results.length) {
        hint.value = q.value;
      }
      // console.log(results.length, 'hits');
      var search_terms = terms.map(escapeRegExp);
      // console.log('Search_terms:', search_terms);
      var re = new RegExp('\\b(' + search_terms.join('|') + ')(\\w+)\\b', 'gi');

      // Because `r` is a DOM element that has already been inserted into
      // the DOM we collect all the `<p>` tags into a Document Fragment
      // and add the whole thing later into the `r` element.
      var p_fragments = document.createDocumentFragment();
      for (i=0, len=results.length; i < len; i++) {
        // var re_already = new RegExp('\\b' + search_terms.join('|') + '\\b', 'gi');
        // console.log('already', re_already.exec(q.value));
        // console.log(results[i][2]);
        var found;
        var matched;

        while ((found = re.exec(results[i][2])) !== null) {
          // console.log('found', found);
          // matched = found[0];
          // console.log('matched', matched);
          matched = new RegExp('\\b' + escapeRegExp(found[0]) + '\\b', 'gi');
          // console.log('found[0]', found[0], matched.test(q.value));

          hint_candidate = found[found.length - 1];
          if (hint_candidate !== undefined && !matched.test(q.value))  {

            if (selected_pointer === i) {
              hint_candidates.push(hint_candidate);
            }
          }
        }

        p = createDomElement('p');
        if (i === selected_pointer) {
          p.classList.add('selected');
        }
        p.dataset.i = i;  // needed by the onmouseover event handler

        a = createDomElement('a', {
          innerHTML: highlightText(results[i][2]),
          href: '/plog/' + results[i][0]
        });
        p.appendChild(a);
        p_fragments.appendChild(p);
        results_ps.push(p);
      }
      r.appendChild(p_fragments);

      // console.log('hint_candidates', hint_candidates);
      // console.log('selected_pointer', selected_pointer);
      if (hint_candidates.length && q.value.charAt(q.value.length - 1) !== ' ') {
        // console.log('LAST CHAR', , 'EOL');
        hint_candidate = hint_candidates[selected_pointer % hint_candidates.length];
        hint.value = q.value + hint_candidate;
      } else {
        hint.value = q.value;
      }

    }

    function _characterFromEvent(e) {
      // for keypress events we should return the character as is
      if (e.type == 'keypress') {
          var character = String.fromCharCode(e.which);
          // console.log('Character keypress:', character);
          return character;
      } else {
        return String.fromCharCode(e.which).toLowerCase();
      }
    }

    function findParentForm(element) {
      var parent = element.parentNode;
      if (parent.nodeName === 'FORM') {
        return parent;
      }
      if (parent === null) {
        throw "too deep. no parent form node to be found";
      }
      return findParentForm(parent);
    }

    function handleKeyboardEvent(name) {
      var i, len;
      if (name === 'tab') {
        if (hint.value !== q.value) {
          q.value = hint.value + ' ';
        }
        if (q.value !== hint.value) {
          handler();  // this starts a new ajax request
        }
      } else if (name === 'down' || name === 'up') {
        if (name === 'down') {
          selected_pointer = Math.min(results_ps.length - 1, ++selected_pointer);
        } else if (name === 'up') {
          selected_pointer = Math.max(0, --selected_pointer);
        }
        for (i=0, len=results_ps.length; i < len; i++) {
          if (i === selected_pointer) {
            results_ps[i].classList.add('selected');
          } else {
            results_ps[i].classList.remove('selected');
          }
        }
        displayResults();
      } else if (name === 'enter') {
        if (results_ps.length) {
          // console.log(results_ps.length, 'results, pointer=', selected_pointer);
          var p = results_ps[selected_pointer];
          var a = p.getElementsByTagName('a')[0];
          q.value = hint.value = a.textContent;
          r.style.display = 'none';
          window.location = a.href;
        } else {
          // We need to submit the form but we can't simply `return true`
          // because the event we're returning to isn't a form submission.
          findParentForm(q).submit();
          return true;
        }
      } else if (name === 'esc') {
        r.style.display = 'none';
      }
      return false;
    }

    function handleKeyEvent(e) {
      var relevant_keycodes = {
        13: 'enter',
        9: 'tab',
        38: 'up',
        40: 'down',
        27: 'esc'
      };
      if (!relevant_keycodes[e.keyCode]) return false;
      e.preventDefault();
      return handleKeyboardEvent(relevant_keycodes[e.keyCode]);
    }

    function handleAjaxError() {
      r.style.display = 'none';
    }

    var cache = {};
    function handler() {
      if (!q.value.trim()) {
        hint.value = '';
        r.style.display = 'none';
        return;
      }
      // new character, let's reset the selected_pointer
      selected_pointer = 0;
      if (cache[q.value.trim()]) {
        var response = cache[q.value.trim()];
        terms = response.terms;
        results = response.results;
        displayResults();
      } else {
        var req;
        if (window.XMLHttpRequest) { // Mozilla, Safari, ...
            req = new XMLHttpRequest();
        } else if (window.ActiveXObject) { // IE 8 and older
            req = new ActiveXObject("Microsoft.XMLHTTP");
        }
        req.onreadystatechange = function() {
          if (req.readyState === 4) {
            if (req.status === 200) {
              var response = JSON.parse(req.responseText);
              cache[q.value.trim()] = response;
              terms = response.terms;
              results = response.results;
              displayResults();
            } else {
              console.warn(req.status, req.responseText);
              handleAjaxError();
            }
          }
        };
        req.open('GET', options.url + encodeURIComponent(q.value.trim()), true);
        req.send();
      }
    }

    function handleBlur(event) {
      // return;
      hint.value = q.value;

      // necessary so it becomes possible to click the links before they
      // disappear too quickly
      setTimeout(function() {
        r.style.display = 'none';
      }, 200);
      event.preventDefault();
    }

    function handleFocus(event) {
      if (q.value.length && results_ps.length) {
        r.style.display = 'block';
      }
    }

    attachHandler(q, 'input', handler);
    attachHandler(q, 'keydown', handleKeyEvent);
    attachHandler(q, 'blur', handleBlur);
    attachHandler(q, 'focus', handleFocus);

    if (q.value.length) {
      handler();
    }

  };  // end of setUp

})(window, document);

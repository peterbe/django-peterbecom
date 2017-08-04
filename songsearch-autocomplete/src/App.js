import React, { Component } from 'react'
import './App.css'
import { throttle } from 'throttle-debounce'

const appendSuggestion = (text, append) => {
  let split = text.split(/\s+/)
  split.pop()
  split.push(append)
  return split.join(' ')
}

class App extends Component {
  state = {
    q: '',
    searching: false,
    // searchMaxLength: null,
    autocompleteSuggestions: null,
    autocompleteHighlight: -1,
    showAutocompleteSuggestions: true
  }

  componentDidMount() {
    // If the <input> HTML had something typed into it when the React
    // app started, that would be passed to the App when initialized.
    // For example if the React app is slow to load. I.e. async slow.
    if (this.props.initialValue && !this.state.q) {
      this.setState({ q: this.props.initialValue })
    }
  }

  submitSearch = event => {
    event.preventDefault()
    this._submit(this.state.q)
  }

  _submit = (q, submitevent = 'enter') => {
    // console.warn("GOTO!!!", 'https://songsear.ch/q/' + q);
    q = q.trim()
    if (!q) {
      return
    }
    let gotoURL = `https://songsear.ch/q/${q}?autocomplete=${submitevent}`
    document.location.href = gotoURL
    if (this.state.autocompleteSuggestions) {
      this.setState({
        autocompleteSuggestions: null,
        autocompleteHighlight: -1,
        showAutocompleteSuggestions: true
      })
    }
  }

  onFocusSearch = event => {
    if (!this.state.showAutocompleteSuggestions) {
      this.setState({ showAutocompleteSuggestions: true })
    }
  }

  onBlurSearch = event => {
    setTimeout(() => {
      this.setState({
        showAutocompleteSuggestions: false
      })
    }, 300)
  }

  onChangeSearch = event => {
    this.setState({ q: event.target.value })
    let length = event.target.value.length
    // if (length > this.refs.q.maxLength - 10) {
    //   this.setState({searchMaxLength: [
    //     length,
    //     this.refs.q.maxLength
    //   ]})
    // } else if (this.state.searchMaxLength) {
    //   this.setState({searchMaxLength: null})
    // }
    if (length > 12) {
      this._fetchAutocompleteSuggestionsThrottledLonger(
        event.target.value.trim()
      )
    } else if (length > 5) {
      this._fetchAutocompleteSuggestionsThrottled(event.target.value.trim())
    } else if (length) {
      this._fetchAutocompleteSuggestions(event.target.value.trim())
    } else {
      this.setState({
        autocompleteSuggestions: null,
        autocompleteHighlight: -1,
        showAutocompleteSuggestions: true
      })
    }
  }

  _last_fetch_term = null

  _fetchAutocompleteSuggestions = q => {
    let url = `https://songsear.ch/api/search/autocomplete?q=${q}`
    this._last_fetch_term = q
    fetch(url).then(r => {
      if (r.status === 200) {
        if (q === this._last_fetch_term) {
          r.json().then(results => {
            this.setState({
              autocompleteSuggestions: results.matches,
              autocompleteHighlight: -1
            })
          })
        }
      }
    })
  }

  _fetchAutocompleteSuggestionsThrottled = throttle(
    500,
    this._fetchAutocompleteSuggestions
  )

  _fetchAutocompleteSuggestionsThrottledLonger = throttle(
    1500,
    this._fetchAutocompleteSuggestions
  )

  onKeyDownSearch = event => {
    let suggestions = this.state.autocompleteSuggestions
    if (suggestions) {
      let highlight = this.state.autocompleteHighlight
      if (event.key === 'Tab') {
        event.preventDefault()
        let suggestion =
          highlight > -1 ? suggestions[highlight] : suggestions[0]
        if (suggestion.append) {
          this.setState({
            q: appendSuggestion(this.state.q, suggestion.text) + ' ',
            autocompleteSuggestions: null,
            autocompleteHighlight: -1
          })
        } else {
          this.setState({
            q: suggestion.text + ' '
          })
          this._fetchAutocompleteSuggestions(suggestion.text)
        }
      } else if (event.key === 'ArrowDown' && highlight < suggestions.length) {
        event.preventDefault()
        this.setState({ autocompleteHighlight: highlight + 1 })
      } else if (event.key === 'ArrowUp' && highlight > -1) {
        this.setState({ autocompleteHighlight: highlight - 1 })
      } else if (event.key === 'Enter') {
        if (highlight > -1) {
          event.preventDefault()
          this.setState(
            {
              q: suggestions[highlight].text,
              autocompleteSuggestions: null,
              autocompleteHighlight: -1
            },
            () => {
              this._submit(suggestions[highlight].text, 'enterkey')
            }
          )
        }
      }
    }
  }

  onSelectSuggestion = (event, suggestion) => {
    event.preventDefault()
    this._submit(suggestion.text, 'clicked')
  }

  render() {
    return (
      <form
        style={{ margin: '50px 0' }}
        action="https://songsear.ch/q/"
        onSubmit={this.submitSearch}
      >
        <div
          className="ui big icon input fluid"
          style={{ display: 'relative' }}
        >
          <input
            type="search"
            name="term"
            value={this.state.q}
            onFocus={this.onFocusSearch}
            onBlur={this.onBlurSearch}
            onChange={this.onChangeSearch}
            onKeyDown={this.onKeyDownSearch}
            className="form-control x-large"
            placeholder="Type your search here..."
          />
          <i className="search icon" />
          {this.state.autocompleteSuggestions &&
          this.state.showAutocompleteSuggestions
            ? <ShowAutocompleteSuggestions
                onSelectSuggestion={this.onSelectSuggestion}
                highlight={this.state.autocompleteHighlight}
                suggestions={this.state.autocompleteSuggestions}
              />
            : null}
        </div>
      </form>
    )
  }
}

export default App

const ShowAutocompleteSuggestions = ({
  highlight,
  suggestions,
  onSelectSuggestion
}) => {
  if (!suggestions.length) {
    return null
  }
  return (
    <div className="autocomplete">
      <ul>
        {suggestions.map((s, index) => {
          let className = index === highlight ? 'active' : ''
          return (
            <li
              key={index}
              className={className}
              onClick={e => onSelectSuggestion(e, s)}
            >
              <p dangerouslySetInnerHTML={{ __html: s.html }} />
            </li>
          )
        })}
      </ul>
    </div>
  )
}

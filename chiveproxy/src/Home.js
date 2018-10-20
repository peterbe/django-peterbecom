import React, { Component } from 'react';
import ky from 'ky';
import { Link, Redirect } from 'react-router-dom';

// import './App.css';

const fetchCache = {};

class Home extends Component {
  state = {
    cards: null,
    loading: true,
    redirectTo: null
  };

  async componentDidMount() {
    let cards;
    if (fetchCache.cards) {
      cards = fetchCache.cards;
    } else {
      const response = await ky('/api/cards/');
      const data = await response.json();
      cards = data.cards;
      fetchCache.cards = cards;
    }

    // console.log(this.props.match.params);
    if (
      Object.keys(this.props.match.params).length === 2 &&
      ['next', 'previous'].includes(this.props.match.params[1])
    ) {
      const current = this.props.match.params[0];
      const direction = this.props.match.params[1];
      console.log('CURRENT', current);
      let previous = null;
      let next = false;
      let redirectTo = null;
      for (const card of cards) {
        // console.log('card:', card);
        if (next) {
          redirectTo = card;
          break;
        }
        if (card.uri === current) {
          if (direction === 'next') {
            next = true;
          } else {
            redirectTo = previous;
            break;
          }
        }
        previous = card;
      }
      this.setState({ redirectTo: redirectTo });
    } else {
      this.setState({ loading: false, cards: cards });
    }
  }
  render() {
    if (this.state.redirectTo) {
      const card = this.state.redirectTo;
      const pathname = `/${card.uri}?url=${encodeURIComponent(card.url)}`;
      console.log('PATHNAME:', pathname);
      return <Redirect to={pathname} push={true} />;
      // return (
      //   <Redirect
      //     to={{
      //       pathname,
      //       state: { from: this.props.location }
      //     }}
      //   />
      // );
    }
    return (
      <div
        className={this.state.loading ? 'is-loading container' : 'container'}
      >
        {this.state.cards && <ShowCards cards={this.state.cards} />}
      </div>
    );
  }
}

export default Home;

class ShowCards extends React.PureComponent {
  componentWillMount() {
    document.title = `(${this.props.cards.length}) Posts`;
  }
  render() {
    const { cards } = this.props;
    return (
      <div className="content">
        {cards.map(card => {
          return (
            <div className="box" key={card.uri}>
              <article className="media">
                <div className="media-content">
                  <h3>
                    <Link
                      to={`/${card.uri}?url=${encodeURIComponent(card.url)}`}
                    >
                      {card.text}
                    </Link>
                  </h3>
                  <Link to={`/${card.uri}?url=${encodeURIComponent(card.url)}`}>
                    <img src={card.img} alt={card.text} />
                  </Link>
                </div>
              </article>
            </div>
          );
        })}
      </div>
    );
  }
}

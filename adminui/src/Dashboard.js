import React from 'react';
import { observer } from 'mobx-react';
import { Header } from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import { Button, Container, Segment } from 'semantic-ui-react';
import store from './Store';

export default observer(
  class Dashboard extends React.Component {
    componentDidMount() {
      document.title = 'Dasboard';
    }

    logIn = event => {
      event.preventDefault();
      this.props.logIn();
    };

    render() {
      return (
        <Container>
          <Header as="h1">Dashboard</Header>
          {!store.user.accessToken ? (
            <Button
              onClick={event => {
                event.preventDefault();
                console.log(this.props);
                this.props.authorize();
              }}
            >
              Log In
            </Button>
          ) : (
            <DashboardLinks />
          )}
        </Container>
      );
    }
  }
);

class DashboardLinks extends React.PureComponent {
  render() {
    return (
      <Segment.Group raised>
        <Segment>
          <Link to="/blogitems">Blogitems</Link>
        </Segment>
        <Segment>
          <Link to="/comments">Comments</Link>
        </Segment>
      </Segment.Group>
    );
  }
}

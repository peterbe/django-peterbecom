import React from 'react';
import { Link } from 'react-router-dom';
import { Container, Header, Button, Segment } from 'semantic-ui-react';

class Dashboard extends React.Component {
  render() {
    return (
      <Container>
        <Header as="h1">Dashboard</Header>
        {!this.props.accessToken ? (
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

class DashboardLinks extends React.PureComponent {
  render() {
    return (
      <Segment.Group raised>
        <Segment>
          <Link to="/plog">Blogitems</Link>
        </Segment>
        <Segment>
          <Link to="/plog/comments">Comments</Link>
        </Segment>
      </Segment.Group>
    );
  }
}

export default Dashboard;

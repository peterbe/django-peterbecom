import React from 'react';
import { Link } from 'react-router-dom';
import { Container, Header, Button, Segment } from 'semantic-ui-react';

class Dashboard extends React.Component {
  componentDidMount() {
    document.title = 'Peterbe.com Admin';
  }
  render() {
    return (
      <Container>
        <Header as="h1">Dashboard</Header>
        {!this.props.user ? (
          <Button
            onClick={(event) => {
              event.preventDefault();
              // console.log(this.props);
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
          <Segment.Group>
            <Segment>
              <Link to="/plog">Blogitems</Link>
            </Segment>
            <Segment>
              <Link to="/plog/add">Add new blogitem</Link>
            </Segment>
            <Segment>
              <Link to="/plog/realtimehits">Realtime Hits</Link>
            </Segment>
            <Segment>
              <Link to="/plog/hits">Hits</Link>
            </Segment>
            <Segment>
              <Link to="/plog/spam/patterns">Spam Comment Patterns</Link>
            </Segment>
          </Segment.Group>
        </Segment>
        <Segment.Group>
          <Segment>
            <Link to="/plog/comments">Comments</Link>
          </Segment>
          <Segment>
            <Link to="/plog/comments?unapproved=only">Unapproved comments</Link>
          </Segment>
          <Segment>
            <Link to="/plog/comments?autoapproved=only">
              Autoapproved comments
            </Link>
          </Segment>
          <Segment>
            <Link to="/plog/comments/counts">Comment Counts</Link>
          </Segment>
          <Segment>
            <Link to="/plog/comments/auto-approved-records">
              Auto Approved Records
            </Link>
          </Segment>
          <Segment>
            <Link to="/plog/comments/geo">Geo Comments</Link>
          </Segment>
        </Segment.Group>
        <Segment>
          <Link to="/postprocessings">Post Processings</Link>
        </Segment>
        <Segment>
          <Link to="/searchresults">Search Results</Link>
        </Segment>
        <Segment>
          <Link to="/cdn">CDN</Link>
        </Segment>
        <Segment>
          <Link to="/lyrics-page-healthcheck">Lyrics Page Healthcheck</Link>
        </Segment>
      </Segment.Group>
    );
  }
}

export default Dashboard;

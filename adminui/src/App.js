import React from 'react';
import './App.css';
import 'semantic-ui-css/semantic.min.css';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import { Container, Dropdown, List, Menu, Segment } from 'semantic-ui-react';

import Dashboard from './Dashboard';
import EditBlogitem from './EditBlogitem';

class App extends React.Component {
  render() {
    return (
      <Router>
        <div>
          <Menu fixed="top" inverted>
            <Container>
              <Menu.Item as="a" header>
                {/* <Image size="mini" src="/logo.png" style={{ marginRight: '1.5em' }} /> */}
                Peterbe.com Admin UI
              </Menu.Item>
              <Menu.Item as="a">Home</Menu.Item>

              <Dropdown item simple text="Dropdown">
                <Dropdown.Menu>
                  <Dropdown.Item>List Item</Dropdown.Item>
                  <Dropdown.Item>List Item</Dropdown.Item>
                  <Dropdown.Divider />
                  <Dropdown.Header>Header Item</Dropdown.Header>
                  <Dropdown.Item>
                    <i className="dropdown icon" />
                    <span className="text">Submenu</span>
                    <Dropdown.Menu>
                      <Dropdown.Item>List Item</Dropdown.Item>
                      <Dropdown.Item>List Item</Dropdown.Item>
                    </Dropdown.Menu>
                  </Dropdown.Item>
                  <Dropdown.Item>List Item</Dropdown.Item>
                </Dropdown.Menu>
              </Dropdown>
            </Container>
          </Menu>

          <Container style={{ marginTop: '7em' }}>
            <Switch>
              <Route path="/" exact component={Dashboard} />
              <Route path="/blogitem/:id" component={EditBlogitem} />
              {/* <Redirect from="/old-match" to="/will-match" /> */}
              {/* <Route path="/will-match" component={WillMatch} /> */}
              <Route component={NoMatch} />
            </Switch>
          </Container>

          <Segment
            inverted
            vertical
            style={{ margin: '5em 0em 0em', padding: '5em 0em' }}
          >
            <Container textAlign="center">
              <List horizontal inverted divided link>
                <List.Item as="a" href="#">
                  Site Map
                </List.Item>
                <List.Item as="a" href="#">
                  Contact Us
                </List.Item>
                <List.Item as="a" href="#">
                  Terms and Conditions
                </List.Item>
                <List.Item as="a" href="#">
                  Privacy Policy
                </List.Item>
              </List>
            </Container>
          </Segment>
        </div>
      </Router>
    );
  }
}

export default App;

const NoMatch = ({ location }) => (
  <div>
    <h3>
      No match for <code>{location.pathname}</code>
    </h3>
  </div>
);

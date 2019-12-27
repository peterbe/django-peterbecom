import React from 'react';
import {
  Button,
  Checkbox,
  Container,
  Header,
  Icon,
  Input,
  Loader,
  Dimmer,
  Segment,
  Message,
  Table
} from 'semantic-ui-react';

import { ShowServerError } from './Common';

class SpamCommentPatterns extends React.Component {
  state = {
    loading: false,
    patterns: null,
    serverError: null,
    deletedPattern: null
  };
  componentDidMount() {
    document.title = 'Spam Comment Patterns';
    this.setState({ loading: true }, this.loadPatterns);
  }

  loadPatterns = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/plog/spam/patterns';
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ loading: false, serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const result = await response.json();
      this.setState({
        loading: false,
        patterns: result.patterns,
        serverError: null
      });
    } else {
      this.setState({ loading: false, serverError: response });
    }
  };
  componentWillUnmount() {
    this.dismounted = true;
  }

  addHandler = async ({ pattern, isRegex, isURLPattern }) => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/plog/spam/patterns';
    const data = {
      pattern,
      is_regex: isRegex,
      is_url_pattern: isURLPattern
    };
    try {
      response = await fetch(url, {
        method: 'POST',
        body: JSON.stringify(data),
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const result = await response.json();
      return this.setState({
        patterns: result.patterns,
        serverError: null
      });
    } else if (response.status === 400) {
      const result = await response.json();
      return this.setState({ serverError: result });
    } else {
      return this.setState({ serverError: response });
    }
  };

  deletePattern = async pattern => {
    if (window.confirm('Are you sure?')) {
      if (!this.props.accessToken) {
        throw new Error('No accessToken');
      }
      let response;
      let url = `/api/v0/plog/spam/patterns/${pattern.id}`;
      try {
        response = await fetch(url, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ serverError: ex });
      }

      if (this.dismounted) {
        return;
      }
      if (response.ok) {
        const result = await response.json();
        return this.setState({
          patterns: result.patterns,
          deletedPattern: pattern,
          serverError: null
        });
      } else {
        return this.setState({ serverError: response });
      }
    }
  };

  render() {
    const { serverError, loading, deletedPattern } = this.state;
    const patterns = this.state.patterns || [];

    return (
      <Container textAlign="center">
        <Header as="h1">Spam Comment Patterns</Header>
        <ShowServerError error={serverError} />
        <Segment basic>
          <Dimmer active={loading} inverted>
            <Loader inverted>Loading</Loader>
          </Dimmer>

          <Table celled>
            <Table.Header>
              <Table.Row>
                <Table.HeaderCell>Pattern</Table.HeaderCell>
                <Table.HeaderCell>Regex</Table.HeaderCell>
                <Table.HeaderCell>URL Pattern</Table.HeaderCell>
                <Table.HeaderCell>Kills</Table.HeaderCell>
                <Table.HeaderCell> </Table.HeaderCell>
              </Table.Row>
            </Table.Header>

            <Table.Body>
              {patterns.map(pattern => {
                return (
                  <Table.Row key={pattern.id}>
                    <Table.Cell>
                      <code>{pattern.pattern}</code>
                    </Table.Cell>
                    <Table.Cell>
                      {pattern.is_regex ? (
                        <Icon name="check" />
                      ) : (
                        <Icon name="dont" />
                      )}
                    </Table.Cell>
                    <Table.Cell>
                      {pattern.is_url_pattern ? (
                        <Icon name="check" />
                      ) : (
                        <Icon name="dont" />
                      )}
                    </Table.Cell>
                    <Table.Cell>{pattern.kills}</Table.Cell>
                    <Table.Cell>
                      <Button
                        color="red"
                        size="small"
                        onClick={event => {
                          this.deletePattern(pattern);
                        }}
                      >
                        Delete
                      </Button>
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>

            <Table.Header>
              <AddFormRow addHandler={this.addHandler} />
            </Table.Header>
          </Table>
        </Segment>

        {deletedPattern && (
          <Message style={{ textAlign: 'left' }}>
            <Message.Header>Deleted</Message.Header>
            <dl>
              <dt>Pattern</dt>
              <dd>
                <code>{deletedPattern.pattern}</code>
              </dd>
              <dt>Regex</dt>
              <dd>
                {deletedPattern.is_regex ? (
                  <Icon name="check" />
                ) : (
                  <Icon name="dont" />
                )}
              </dd>
              <dt>URL Pattern</dt>
              <dd>
                {deletedPattern.is_url_pattern ? (
                  <Icon name="check" />
                ) : (
                  <Icon name="dont" />
                )}
              </dd>
            </dl>
          </Message>
        )}
      </Container>
    );
  }
}

export default SpamCommentPatterns;

function AddFormRow({ addHandler }) {
  const [pattern, setPattern] = React.useState('');
  const [isRegex, setIsRegex] = React.useState(false);
  const [isURLPattern, setIsURLPattern] = React.useState(false);

  return (
    <Table.Row>
      <Table.HeaderCell>
        <Input
          fluid
          value={pattern}
          onChange={(event, data) => {
            setPattern(data.value);
          }}
        />
      </Table.HeaderCell>
      <Table.HeaderCell>
        <Checkbox
          defaultChecked={isRegex}
          onChange={(event, data) => {
            setIsRegex(data.checked);
          }}
          toggle
        />
      </Table.HeaderCell>
      <Table.HeaderCell>
        <Checkbox
          defaultChecked={isURLPattern}
          onChange={(event, data) => {
            setIsURLPattern(data.checked);
          }}
          toggle
        />
      </Table.HeaderCell>
      <Table.HeaderCell colSpan={2}>
        <Button
          primary
          disabled={!pattern.trim()}
          onClick={event => {
            if (pattern) {
              addHandler({
                pattern,
                isRegex,
                isURLPattern
              }).then(() => {
                setPattern('');
                setIsRegex(false);
                setIsURLPattern(false);
              });
            }
          }}
        >
          Add
        </Button>
      </Table.HeaderCell>
    </Table.Row>
  );
}

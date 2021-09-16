import React from 'react';
import { Container, Table, Header } from 'semantic-ui-react';

import { ShowServerError } from './Common';

class CommentAutoApproveds extends React.Component {
  state = {
    loading: false,
    data: null,
    serverError: null,
  };
  componentDidMount() {
    document.title = 'Comment Auto Approved Records';
    this.setState({ loading: true }, this.loadData);
  }

  componentWillUnmount() {
    this.dismounted = true;
  }

  loadData = async () => {
    // if (!this.props.accessToken) {
    //   throw new Error('No accessToken');
    // }
    let response;
    let url = '/api/v0/plog/comments/auto-approved-records/';
    try {
      response = await fetch(url, {
        // headers: {
        //   Authorization: `Bearer ${this.props.accessToken}`
        // }
      });
    } catch (ex) {
      return this.setState({ loading: false, serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const data = await response.json();
      this.setState({
        loading: false,
        data,
        serverError: null,
      });
    } else {
      this.setState({ loading: false, serverError: response });
    }
  };

  render() {
    const { data, serverError, loading } = this.state;
    return (
      <Container textAlign="center">
        <Header as="h1">Comment Auto Approved Records</Header>
        <ShowServerError error={serverError} />
        <small>{loading ? 'loading...' : ''}</small>
        {!loading && data && (
          <ShowAutoApproveGoodComments records={data.records} />
        )}
      </Container>
    );
  }
}

export default CommentAutoApproveds;

function ShowAutoApproveGoodComments({ records }) {
  if (!records || !records.records.length) {
    return (
      <p>
        <i>No previous auto-approve-good-comments records</i>
      </p>
    );
  }
  return (
    <div style={{ marginBottom: 20 }}>
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>When</Table.HeaderCell>
            <Table.HeaderCell>Time ago</Table.HeaderCell>
            <Table.HeaderCell>Auto-approved comments</Table.HeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {records.records.map((record) => {
            return (
              <Table.Row key={record.date}>
                <Table.Cell>{record.date}</Table.Cell>
                <Table.Cell>{record.human} ago</Table.Cell>
                <Table.Cell>{record.count}</Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
      {!!records.median_frequency_minutes && (
        <p>
          Frequency: every <b>{records.median_frequency_minutes}</b> minutes
        </p>
      )}
      {records.next_run && (
        <p>
          Next run: <b>{records.next_run.date}</b> (approximately{' '}
          {(records.next_run.minutes / 60).toFixed(1)} hours from now)
        </p>
      )}
    </div>
  );
}

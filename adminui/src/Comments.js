import React from 'react';
import md5 from 'md5';
import {
  Button,
  Checkbox,
  Container,
  Loader,
  Comment,
  Flag,
  Header,
  Icon,
  Input,
  Message,
  TextArea,
  Form
} from 'semantic-ui-react';
import { DisplayDate, ShowServerError } from './Common';
import { BASE_URL } from './Config';

class Comments extends React.Component {
  state = {
    comments: null,
    count: 0,
    oldest: null,
    serverError: null,
    loading: false,
    search: (() => {
      const hash = this.props.location.hash;
      if (hash) {
        const regex = /search=(.*)/;
        if (regex.test(hash)) {
          const search = [...regex.exec(hash)][1];
          document.location.hash = '';
          return search;
        }
      }
      return '';
    })(),
    unapprovedOnly: false,
    checkedForApproval: {},
    checkedForDelete: {},
    editing: {},
    approved: {},
    deleted: {},
    deleting: {},
    approving: {}
  };
  componentDidMount() {
    document.title = 'Comments';
    this.fetchComments();
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevState.count !== this.state.count) {
      document.title = `(${this.state.count.toLocaleString()}) Comments`;
    }
  }

  fetchComments = async (loadMore = false) => {
    !this.state.loading && this.setState({ loading: true });
    const { accessToken } = this.props;
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    const { oldest, search } = this.state;
    let url = `/api/v0/plog/comments/?search=${encodeURIComponent(search)}`;
    if (loadMore) {
      url += `&since=${encodeURIComponent(oldest)}`;
    }
    if (this.state.unapprovedOnly) {
      url += '&unapproved=only';
    }
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });
    if (response.ok) {
      const data = await response.json();
      this.setState({
        comments: data.comments,
        count: data.count,
        oldest: data.oldest,
        loading: false
      });
    } else {
      this.setState({ serverError: response, loading: false });
    }
  };

  deleteComments = async oids => {
    const deleting = {};
    oids.forEach(oid => {
      deleting[oid] = true;
    });
    this.setState({ loading: true, deleting }, async () => {
      await this._deleteOrApproveComments('delete', { oids });
      const deleted = Object.assign({}, this.state.deleted);
      oids.forEach(oid => {
        deleted[oid] = true;
      });
      this.setState({ deleting: {}, deleted }, () => {
        this._resetChecked(oids);
      });
    });
  };

  approveComments = async oids => {
    const approving = {};
    oids.forEach(oid => {
      approving[oid] = true;
    });
    this.setState({ loading: true, approving }, async () => {
      await this._deleteOrApproveComments('approve', { oids });
      const approved = Object.assign({}, this.state.approved);
      oids.forEach(oid => {
        approved[oid] = true;
      });
      this.setState({ approving: {}, approved }, () => {
        this._resetChecked(oids);
      });
    });
  };

  _resetChecked = oids => {
    const checkedForApproval = this.state.checkedForApproval;
    const checkedForDelete = this.state.checkedForDelete;
    oids.forEach(oid => {
      delete checkedForApproval[oid];
      delete checkedForDelete[oid];
    });
    this.setState({ checkedForApproval, checkedForDelete });
  };

  _deleteOrApproveComments = async (type, data) => {
    const { accessToken } = this.props;
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    if (!(type === 'delete' || type === 'approve')) {
      throw new Error(`Invalid endpoint ${type}`);
    }
    const url = `/api/v0/plog/comments/${type}/`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`
        },
        body: JSON.stringify(data)
      });
      if (response.ok) {
        this.setState({
          loading: false,
          serverError: null
        });
      } else {
        this.setState({ serverError: response, loading: false });
      }
    } catch (ex) {
      this.setState({ serverError: ex, loading: false });
    }
  };

  editComment = async (comment, data) => {
    this.setState({ loading: true });

    const { accessToken } = this.props;
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    // const data = { comment: text, oid: comment.oid };
    // Correct the alias
    data.comment = data.text;
    data.oid = comment.oid;
    const url = `/api/v0/plog/comments/`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`
        },
        body: JSON.stringify(data)
      });
      if (response.ok) {
        const data = await response.json();
        function mutateCommentTexts(comments) {
          comments.forEach(c => {
            if (c.oid === comment.oid) {
              c.comment = data.comment;
              c.name = data.name;
              c.email = data.email;
              c.rendered = data.rendered;
              c._clues = data._clues;
            } else {
              mutateCommentTexts(c.replies);
            }
          });
        }
        const comments = this.state.comments;
        mutateCommentTexts(comments);
        const editing = Object.assign({}, this.state.editing);
        editing[comment.oid] = false;
        this.setState({
          comments,
          editing,
          loading: false,
          serverError: null
        });
      } else {
        this.setState({ serverError: response, loading: false });
      }
    } catch (ex) {
      console.error(ex);
      this.setState({ serverError: ex, loading: false });
    }
  };

  render() {
    return (
      <Container>
        <ShowServerError error={this.state.serverError} />
        {this.state.comments === null && this.state.serverError === null ? (
          <Loader
            active
            size="massive"
            inline="centered"
            content="Loading Comments..."
            style={{ margin: '200px 0' }}
          />
        ) : null}

        {this.state.comments && (
          <form
            onSubmit={event => {
              event.preventDefault();
              this.setState(
                { search: this.refs.q.inputRef.value },
                this.fetchComments
              );
            }}
          >
            <Input
              ref="q"
              action={{ icon: 'search' }}
              fluid
              defaultValue={this.state.search || ''}
              placeholder="Search filter..."
            />
            <Checkbox
              toggle
              defaultChecked={this.state.unapprovedOnly}
              onChange={(event, data) => {
                this.setState(
                  { unapprovedOnly: data.checked },
                  this.fetchComments
                );
              }}
              label="Unapproved only"
            />
          </form>
        )}
        {
          <Checked
            checkedForApproval={this.state.checkedForApproval}
            checkedForDelete={this.state.checkedForDelete}
            deleteComments={this.deleteComments}
            approveComments={this.approveComments}
          />
        }
        {this.state.comments && (
          <CommentsTree
            comments={this.state.comments}
            count={this.state.count}
            loading={this.state.loading}
            editing={this.state.editing}
            approving={this.state.approving}
            deleting={this.state.deleting}
            approved={this.state.approved}
            deleted={this.state.deleted}
            editComment={this.editComment}
            approveComment={oid => {
              this.approveComments([oid]);
            }}
            deleteComment={oid => {
              this.deleteComments([oid]);
            }}
            checkedForApproval={this.state.checkedForApproval}
            checkedForDelete={this.state.checkedForDelete}
            setCheckedForApproval={(oid, toggle) => {
              const checkedForApproval = Object.assign(
                {},
                this.state.checkedForApproval
              );
              checkedForApproval[oid] = toggle;
              this.setState({ checkedForApproval });
            }}
            setCheckedForDelete={(oid, toggle) => {
              const checkedForDelete = Object.assign(
                {},
                this.state.checkedForDelete
              );
              checkedForDelete[oid] = toggle;
              this.setState({ checkedForDelete });
            }}
            setEditing={oid => {
              const editing = Object.assign({}, this.state.editing);
              editing[oid] = !editing[oid];
              this.setState({ editing });
            }}
            updateFilterSearch={search => {
              const ref = this.refs.q.inputRef;
              if (ref.value && ref.value.includes(search)) {
                ref.value = ref.value.replace(search, '');
                search = ref.value;
              } else {
                ref.value += ` ${search}`;
                ref.value = ref.value.trim();
                search = ref.value;
              }
              this.setState({ search }, this.fetchComments);
            }}
          />
        )}
        {this.state.comments && (
          <Button
            fluid
            type="text"
            onClick={event => {
              this.fetchComments(true);
              window.scrollTo(0, 0);
            }}
          >
            Load more... (older than {this.state.oldest})
          </Button>
        )}
      </Container>
    );
  }
}

export default Comments;

class Checked extends React.Component {
  render() {
    const {
      checkedForApproval,
      checkedForDelete,
      approveComments,
      deleteComments
    } = this.props;
    const oidsForApproval = Object.entries(checkedForApproval)
      .filter(([_, value]) => value)
      .map(([key, _]) => key);
    const oidsForDelete = Object.entries(checkedForDelete)
      .filter(([_, value]) => value)
      .map(([key, _]) => key);
    if (!oidsForApproval.length && !oidsForDelete.length) return null;
    return (
      <Message>
        <Message.Header>Batch Operation</Message.Header>
        <Button.Group widths="2">
          {oidsForApproval.length && (
            <Button
              positive
              type="text"
              onClick={event => {
                approveComments(oidsForApproval);
              }}
            >
              Approve all ({oidsForApproval.length})
            </Button>
          )}

          {oidsForDelete.length && (
            <Button
              negative
              type="text"
              onClick={event => {
                deleteComments(oidsForDelete);
              }}
            >
              Delete all ({oidsForDelete.length})
            </Button>
          )}
        </Button.Group>
      </Message>
    );
  }
}

class CommentsTree extends React.PureComponent {
  render() {
    const { comments, count } = this.props;

    let lastBlogitem = null;
    return (
      <Comment.Group>
        <Header as="h2" dividing>
          {count.toLocaleString()} Comments
        </Header>

        {comments.map(comment => {
          const differentBlogitem = lastBlogitem !== comment.blogitem.id;
          lastBlogitem = comment.blogitem.id;
          return (
            <CommentTree
              key={comment.id}
              comment={comment}
              root={true}
              showBlogitem={differentBlogitem}
              addToSearch={term => {
                this.props.updateFilterSearch(term);
              }}
              {...this.props}
            />
          );
        })}
      </Comment.Group>
    );
  }
}

class CommentTree extends React.PureComponent {
  static defaultProps = {
    root: false,
    showBlogitem: false
  };
  hotness = seconds => {
    if (seconds < 60) {
      return '🔥🔥🔥';
    } else if (seconds < 60 * 60) {
      return '🔥';
    } else if (seconds < 60 * 60 * 24) {
      return '🔥';
    }
    return '';
  };

  gravatarSrc = comment => {
    let default_ = `https://api.adorable.io/avatars/35/${comment.name ||
      comment.oid}.png`;
    if (comment.email) {
      return `https://www.gravatar.com/avatar/${md5(
        comment.email
      )}?d=${encodeURIComponent(default_)}&s=35`;
    }
    return default_;
  };
  render() {
    const {
      comment,
      root,
      showBlogitem,
      addToSearch,
      checkedForApproval,
      checkedForDelete,
      setCheckedForApproval,
      setCheckedForDelete,
      setEditing,
      editing,
      editComment,
      approveComment,
      deleteComment,
      deleted,
      approved,
      deleting,
      approving
    } = this.props;

    return (
      <Comment>
        {root && showBlogitem && (
          <Header as="h4" dividing>
            <a
              href={BASE_URL + comment.blogitem._absolute_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {comment.blogitem.title}
            </a>
            <Icon
              color="grey"
              style={{ display: 'inline', cursor: 'pointer' }}
              size="mini"
              name="search"
              onClick={event => {
                event.preventDefault();
                addToSearch(`blogitem:${comment.blogitem.oid}`);
              }}
            />
          </Header>
        )}

        <Comment.Avatar src={this.gravatarSrc(comment)} />
        <Comment.Content>
          <Comment.Author as="a">
            {comment.name || <i>No name</i>}{' '}
            {comment.email ? `<${comment.email}>` : <i>No email</i>}{' '}
            {comment.location && comment.location.country_code && (
              <Flag
                name={comment.location.country_code.toLowerCase()}
                title={JSON.stringify(comment.location, null, 2)}
              />
            )}
          </Comment.Author>
          <Comment.Metadata>
            <div>
              {this.hotness(comment.age_seconds)}
              <a
                href={
                  BASE_URL + comment.blogitem._absolute_url + `#${comment.oid}`
                }
                target="_blank"
                rel="noopener noreferrer"
              >
                <DisplayDate date={comment.add_date} />
              </a>{' '}
            </div>
          </Comment.Metadata>
          <Comment.Text>
            {editing[comment.oid] ? (
              <EditComment comment={comment} editComment={editComment} />
            ) : (
              <p dangerouslySetInnerHTML={{ __html: comment.rendered }} />
            )}

            {!comment.approved && !editing[comment.oid] && (
              <p>
                Clues: <code>{JSON.stringify(comment._clues)}</code>
              </p>
            )}
          </Comment.Text>
          <Comment.Actions style={{ fontSize: '1em' }}>
            <Comment.Action>
              {comment.replies.length}{' '}
              {comment.replies.length === 1 ? 'reply' : 'replies'}
            </Comment.Action>
            <Comment.Action>
              <Button
                type="checkbox"
                onClick={event => {
                  setEditing(comment.oid);
                }}
                size="mini"
              >
                {editing[comment.oid] ? 'Cancel' : 'Edit'}
              </Button>
            </Comment.Action>
            {!comment.approved && deleted[comment.oid] && (
              <b style={{ color: '#db2828' }}>Deleted!</b>
            )}
            {!comment.approved && approved[comment.oid] && (
              <b style={{ color: '#21ba45' }}>Approved!</b>
            )}
            {!comment.approved &&
              !(deleted[comment.oid] || approved[comment.oid]) && (
                <Comment.Action>
                  <Checkbox
                    value={comment.oid}
                    checked={!!checkedForApproval[comment.oid]}
                    onChange={(_, data) => {
                      setCheckedForApproval(comment.oid, data.checked);
                    }}
                    style={{ paddingRight: 30, paddingLeft: 10 }}
                  />
                  <Button
                    disabled={
                      deleted[comment.oid] ||
                      approved[comment.oid] ||
                      deleting[comment.oid]
                    }
                    positive
                    loading={!!approving[comment.oid]}
                    onClick={event => {
                      event.preventDefault();
                      approveComment(comment.oid);
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    disabled={
                      deleted[comment.oid] ||
                      approved[comment.oid] ||
                      approving[comment.oid]
                    }
                    negative
                    loading={!!deleting[comment.oid]}
                    onClick={event => {
                      event.preventDefault();
                      deleteComment(comment.oid);
                    }}
                  >
                    Delete
                  </Button>
                  <Checkbox
                    value={comment.oid}
                    checked={!!checkedForDelete[comment.oid]}
                    onChange={(_, data) => {
                      setCheckedForDelete(comment.oid, data.checked);
                    }}
                    style={{ paddingRight: 30, paddingLeft: 10 }}
                  />
                </Comment.Action>
              )}
          </Comment.Actions>
        </Comment.Content>

        {comment.replies.length ? (
          <Comment.Group>
            {comment.replies.map(reply => (
              <CommentTree
                comment={reply}
                key={reply.id}
                checkedForApproval={checkedForApproval}
                checkedForDelete={checkedForDelete}
                setCheckedForApproval={setCheckedForApproval}
                setCheckedForDelete={setCheckedForDelete}
                setEditing={setEditing}
                approveComment={approveComment}
                deleteComment={deleteComment}
                editComment={editComment}
                editing={editing}
                approving={approving}
                deleting={deleting}
                approved={approved}
                deleted={deleted}
              />
            ))}
          </Comment.Group>
        ) : null}
      </Comment>
    );
  }
}

class EditComment extends React.PureComponent {
  state = {
    text: this.props.comment.comment,
    name: this.props.comment.name || '',
    email: this.props.comment.email || ''
  };
  render() {
    return (
      <Form
        onSubmit={event => {
          event.preventDefault();
          this.props.editComment(this.props.comment, {
            text: this.state.text,
            name: this.state.name,
            email: this.state.email
          });
        }}
      >
        <Input
          value={this.state.name}
          onChange={(_, data) => {
            this.setState({ name: data.value });
          }}
          placeholder="Name..."
        />
        <Input
          value={this.state.email}
          onChange={(_, data) => {
            this.setState({ email: data.value });
          }}
          placeholder="Email..."
        />
        <TextArea
          value={this.state.text}
          onChange={(_, data) => {
            this.setState({ text: data.value });
          }}
        />
        <Button primary>Save</Button>
      </Form>
    );
  }
}

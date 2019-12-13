import React from 'react';
import {
  Divider,
  Button,
  Card,
  Message,
  Container,
  Breadcrumb,
  Image,
  Loader,
  Icon,
  Input,
  Form,
  Checkbox,
  TextArea,
  Select,
  Statistic
} from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import { addHours } from 'date-fns/esm';
import { CopyToClipboard } from 'react-copy-to-clipboard';
import { toast } from 'react-semantic-toasts';

import 'codemirror/lib/codemirror.css'; // codemirror
import 'tui-editor/dist/tui-editor.css'; // editor ui
import 'tui-editor/dist/tui-editor-contents.css'; // editor content
import 'highlight.js/styles/github.css'; // code block highlight

import './Editor-overrides.css';

import Editor from 'tui-editor';

import 'tui-editor/dist/tui-editor-extTable.js';
import 'tui-editor/dist/tui-editor-extScrollSync.js';

import { ShowServerError, BlogitemBreadcrumb } from './Common';
import { BASE_URL } from './Config';

export class EditBlogitem extends React.Component {
  state = {
    blogitem: null,
    allCategories: null,
    serverError: null,
    updated: null,
    validationErrors: null,
    preview: null,
    loading: true
  };

  componentWillUnmount() {
    this.dismounted = true;
  }

  componentDidMount() {
    document.title = 'Edit Blogitem';
    this.fetchBlogitem(this.props.match.params.oid);
    this.fetchAllCategories();
  }

  fetchAllCategories = async () => {
    const cacheKey = 'allCategories';
    const allCategories = localStorage.getItem(cacheKey);
    if (allCategories) {
      this.setState({ allCategories: JSON.parse(allCategories) });
    }
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    try {
      const response = await fetch('/api/v0/categories', {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
      if (this.dismounted) return;
      if (response.ok) {
        const json = await response.json();
        this.setState({ allCategories: json.categories }, () => {
          localStorage.setItem(
            cacheKey,
            JSON.stringify(this.state.allCategories)
          );
        });
      } else {
        this.setState({ serverError: response });
      }
    } catch (ex) {
      this.setState({ serverError: ex });
    }
  };

  fetchBlogitem = async oid => {
    let response;
    try {
      response = await fetch(`/api/v0/plog/${encodeURIComponent(oid)}`, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ serverError: ex, loading: false });
    }
    if (this.dismounted) return;
    if (!response.ok) {
      return this.setState({ serverError: response, loading: false });
    }
    const json = await response.json();
    this.setState({ blogitem: json.blogitem, loading: false });
  };

  previewBlogitem = async data => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    try {
      response = await fetch(`/api/v0/plog/preview/`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.props.accessToken}`
        },
        body: JSON.stringify(data)
      });
      if (this.dismounted) return;
    } catch (ex) {
      return this.setState({ serverError: ex });
    }
    if (!response.ok) {
      return this.setState({ serverError: response.status });
    }
    const result = await response.json();
    this.setState({ preview: result.blogitem });
  };

  updateBlogitem = async data => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.state.blogitem.oid;
    let response;
    try {
      response = await fetch(`/api/v0/plog/${oid}`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.props.accessToken}`
        },
        body: JSON.stringify(data)
      });
    } catch (ex) {
      return this.setState({ serverError: ex }, () => {
        toast({
          type: 'error',
          title: 'Server Error!',
          time: 5000
        });
      });
    }
    if (response.ok) {
      const data = await response.json();
      const newOid = data.blogitem.oid !== this.state.blogitem.oid;

      this.setState(
        {
          blogitem: data.blogitem,
          validationErrors: null,
          serverError: null
        },
        () => {
          toast({
            type: 'success',
            title: 'Successfully updated',
            time: 5000,
            size: null // https://github.com/academia-de-codigo/react-semantic-toasts/issues/40
          });
        }
      );
      if (newOid) {
        window.location.href = `/plog/${data.blogitem.oid}`;
      }
    } else if (response.status === 400) {
      const data = await response.json();
      this.setState(
        { serverError: null, validationErrors: data.errors },
        () => {
          toast({
            type: 'warning',
            title: 'Validation Errors!',
            time: 5000
          });
        }
      );
    } else {
      this.setState({ serverError: response.status }, () => {
        toast({
          type: 'error',
          title: 'Server Error!',
          time: 5000
        });
      });
    }
  };

  render() {
    const { blogitem } = this.state;
    if (!this.state.serverError && !blogitem) {
      return (
        <Container>
          <Loader
            active
            size="massive"
            inline="centered"
            content="Loading Blogitem..."
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    return (
      <Container>
        <BlogitemBreadcrumb blogitem={blogitem} page="edit" />
        <ShowServerError error={this.state.serverError} />
        {this.state.validationErrors && (
          <Message negative>
            <Message.Header>Validation Errors</Message.Header>
            <div>
              <pre>
                {JSON.stringify(this.state.validationErrors, undefined, 2)}
              </pre>
            </div>
          </Message>
        )}
        {blogitem && (
          <EditForm
            accessToken={this.props.accessToken}
            blogitem={blogitem}
            allCategories={this.state.allCategories}
            validationErrors={this.state.validationErrors}
            onLoadPreview={async data => {
              this.previewBlogitem(data, this.props.accessToken);
            }}
            onSubmitData={data => {
              this.setState({ updated: null });
              this.updateBlogitem(data, this.props.accessToken);
            }}
          />
        )}
        <PreviewBlogitem data={this.state.preview} />

        {this.state.blogitem && (
          <BlogitemHits
            accessToken={this.props.accessToken}
            blogitem={blogitem}
          />
        )}
      </Container>
    );
  }
}

export class AddBlogitem extends EditBlogitem {
  state = {
    skeleton: {
      oid: '',
      title: '',
      summary: '',
      text: '',
      url: '',
      // pub_date: format(new Date(), 'YYYY-MM-dd HH:MM:ss'),
      pub_date: addHours(new Date(), 1).toISOString(),
      display_format: 'markdown',
      categories: [],
      keywords: []
    }
  };
  componentDidMount() {
    document.title = 'Add Blogitem';

    this.fetchAllCategories(this.props.accessToken);
  }

  createBlogitem = async data => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    try {
      response = await fetch(`/api/v0/plog/`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.props.accessToken}`
        },
        body: JSON.stringify(data)
      });
    } catch (err) {
      return this.setState({ serverError: err });
    }
    if (response.ok) {
      const data = await response.json();
      this.setState(
        { updated: new Date(), validationErrors: null, serverError: null },
        () => {
          window.location.href = `/plog/${data.blogitem.oid}`;
        }
      );
    } else if (response.status === 400) {
      const data = await response.json();
      this.setState(
        { validationErrors: data.errors, serverError: null },
        () => {
          toast({
            type: 'warning',
            title: 'Validation Error!',
            time: 5000
          });
        }
      );
    } else {
      this.setState({ serverError: response.status });
    }
  };

  render() {
    return (
      <Container>
        <Breadcrumb>
          <Breadcrumb.Section>
            <Link to="/plog">Blogitems</Link>
          </Breadcrumb.Section>
          <Breadcrumb.Divider />
          <Breadcrumb.Section active>Add</Breadcrumb.Section>
        </Breadcrumb>
        <ShowServerError error={this.state.serverError} />
        {this.state.validationErrors && (
          <Message negative>
            <Message.Header>Validation Errors</Message.Header>
            <div>
              <pre>
                {JSON.stringify(this.state.validationErrors, undefined, 2)}
              </pre>
            </div>
          </Message>
        )}
        <EditForm
          blogitem={this.state.skeleton}
          allCategories={this.state.allCategories}
          validationErrors={this.state.validationErrors}
          onLoadPreview={async data => {}}
          onSubmitData={async data => {
            sessionStorage.setItem(
              'AddBlogitem',
              JSON.stringify(data, null, 2)
            );
            console.warn(
              "If anything goes wrong, you can recover from 'sessionStorage.AddBlogitem'."
            );
            this.createBlogitem(data);
          }}
        />
      </Container>
    );
  }
}

function slugify(s) {
  return s
    .trim()
    .replace(/\s+/gi, '-')
    .replace(/['?]/g, '')
    .toLowerCase();
}

class EditForm extends React.PureComponent {
  state = {
    hideLabels: JSON.parse(localStorage.getItem('hideLabels') || 'false'),
    showUnimportantFields: false,
    saving: false,
    categories: null,
    useTuiEditor: window.sessionStorage.getItem('useTuiEditor') ? true : false,
    summaryTouched: false
  };

  componentDidMount() {
    this.copyToState(this.props.blogitem);
    this.setCategories(this.props.blogitem.categories);
  }

  componentDidUpdate(prevProps) {
    if (prevProps.blogitem !== this.props.blogitem) {
      this.copyToState(this.props.blogitem);
      this.setCategories(this.props.blogitem.categories);
    }
  }

  copyToState = blogitem => {
    const data = {};
    const simpleKeys = [
      'oid',
      'title',
      'url',
      'pub_date',
      'text',
      'summary',
      'display_format',
      'codesyntax'
    ];
    simpleKeys.forEach(key => {
      data[key] = blogitem[key] || '';
    });
    data.keywords = blogitem.keywords.join('\n');
    data.disallow_comments = blogitem.disallow_comments;
    data.hide_comments = blogitem.hide_comments;
    this.setState(data);
  };

  setCategories = categories => {
    this.setState({ categories: categories.map(category => category.id) });
  };

  onTextBlur = () => {
    this._submit(true);
  };

  submitForm = event => {
    event.preventDefault();
    this._submit();
  };

  _submit = (preview = false) => {
    const data = this.state;

    if (preview) {
      this.props.onLoadPreview(data);
    } else {
      this.props.onSubmitData(data);
    }
  };

  // Assume the OID input field has not been manually edited.
  oidTouched = false;

  handleChange = (e, { name, value }) => {
    this.setState({ [name]: value });
  };

  render() {
    const { blogitem, allCategories } = this.props;
    const { hideLabels, showUnimportantFields } = this.state;
    let { validationErrors } = this.props;
    if (!validationErrors) {
      validationErrors = {};
    }

    let categoryOptions = [];
    if (allCategories) {
      categoryOptions = allCategories.map(cat => ({
        key: cat.id,
        text: `${cat.name} (${cat.count})`,
        name: cat.name,
        value: cat.id
      }));
    }
    // const keywords = blogitem.keywords.map(keyword => keyword);
    // this.categories = blogitem.categories.map(category => category.id);
    // const displayFormat = blogitem.display_format;
    const displayFormatOptions = ['markdown', 'structuredtext'].map(o => {
      return { key: o, text: o, name: o, value: o };
    });

    return (
      <Form onSubmit={this.submitForm}>
        <h3>
          <a href={BASE_URL + blogitem._absolute_url}>{blogitem.title}</a>
        </h3>
        {blogitem.oid && (
          <Thumbnails accessToken={this.props.accessToken} oid={blogitem.oid} />
        )}
        <p style={{ textAlign: 'right' }}>
          <Button
            size="mini"
            secondary={!this.state.hideLabels}
            onClick={event => {
              event.preventDefault();
              this.setState({ hideLabels: !this.state.hideLabels }, () => {
                localStorage.setItem(
                  'hideLabels',
                  JSON.stringify(this.state.hideLabels)
                );
              });
            }}
          >
            {hideLabels ? 'Show labels' : 'Hide labels'}
          </Button>
          <Button
            size="mini"
            secondary={showUnimportantFields}
            onClick={event => {
              event.preventDefault();
              this.setState({
                showUnimportantFields: !showUnimportantFields
              });
            }}
          >
            {showUnimportantFields ? 'Hide some fields' : 'Show all fields'}
          </Button>
        </p>
        <Form.Field>
          {!hideLabels ? <label>OID</label> : null}
          <Input
            name="oid"
            value={this.state.oid || ''}
            error={!!validationErrors.oid}
            placeholder="OID..."
            onChange={(event, data) => {
              // data.oid = event
              if (!this.oidTouched) {
                this.oidTouched = true;
              }
              this.handleChange(event, data);
            }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Title</label> : null}
          <Input
            name="title"
            value={this.state.title || ''}
            error={!!validationErrors.title}
            placeholder="Title..."
            onChange={(event, data) => {
              if (!this.oidTouched && !this.props.blogitem.oid) {
                this.setState({ oid: slugify(data.value) });
              }
              this.handleChange(event, data);
            }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Text</label> : null}
          {this.state.useTuiEditor ? (
            <TuiEditor
              onBlur={() => {
                this.onTextBlur();
              }}
              onChange={text => {
                this.setState({ text });
              }}
              initial={this.state.text || ''}
            />
          ) : null}
          <TextArea
            name="text"
            className="monospaced"
            rows={25}
            onBlur={event => {
              event.preventDefault(); // is this needed?
              this.onTextBlur();
            }}
            value={this.state.text || ''}
            onChange={this.handleChange}
            style={{
              overscrollBehaviorY: 'contain',
              display: this.state.useTuiEditor ? 'none' : null
            }}
          />
          <Button
            size="mini"
            onClick={event => {
              event.preventDefault();
              this.setState({ useTuiEditor: !this.state.useTuiEditor }, () => {
                if (this.state.useTuiEditor) {
                  window.sessionStorage.setItem('useTuiEditor', 'true');
                } else {
                  window.sessionStorage.removeItem('useTuiEditor');
                }
              });
            }}
          >
            Toggle Editor
          </Button>
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Summary</label> : null}
          <TextArea
            name="summary"
            placeholder="Optional summary..."
            rows={4}
            value={this.state.summary || ''}
            onChange={(event, data) => {
              if (!this.state.summaryTouched) {
                this.setState({ summaryTouched: true });
              }
              this.handleChange(event, data);
            }}
          />
          {!this.state.summaryTouched && (
            <Button
              size="mini"
              onClick={event => {
                event.preventDefault();
                let summary = this.state.text.split(/\n\n+/)[0];
                while (summary.startsWith('*') && summary.endsWith('*')) {
                  summary = summary.slice(1, summary.length - 1);
                }
                this.setState({ summary: summary.trim() });
              }}
            >
              Suggest Summary
            </Button>
          )}
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>URL</label> : null}
          <Input
            name="url"
            placeholder="URL"
            value={this.state.url || ''}
            onChange={this.handleChange}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Pub Date</label> : null}
          <Input
            name="pub_date"
            placeholder="Pub date"
            value={this.state.pub_date || ''}
            onChange={this.handleChange}
            error={!!validationErrors.pub_date}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Categories</label> : null}
          <Select
            name="categories"
            value={this.state.categories}
            options={categoryOptions}
            selection
            multiple
            onChange={(event, data) => {
              this.setState({ categories: data.value });
            }}
            renderLabel={item => item.name}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Keywords</label> : null}
          <TextArea
            name="keywords"
            placeholder="Keywords"
            rows={5}
            onChange={this.handleChange}
            value={this.state.keywords || ''}
          />
        </Form.Field>
        {showUnimportantFields ? (
          <Form.Field>
            {!hideLabels ? <label>Display Format</label> : null}
            <Select
              name="display_format"
              error={!!validationErrors.display_format}
              options={displayFormatOptions}
              selection
              onChange={this.handleChange}
              renderLabel={item => item.name}
              value={this.state.display_format || ''}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            {!hideLabels ? <label>Code Syntax</label> : null}
            <Input
              name="codesyntax"
              placeholder="Code Syntax"
              onChange={this.handleChange}
              value={this.state.codesyntax || ''}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            <Checkbox
              label="Disallow comments"
              name="disallow_comments"
              checked={this.state.disallow_comments}
              onChange={(event, data) => {
                this.handleChange(event, { value: data.checked, ...data });
              }}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            <Checkbox
              label="Hide comments"
              name="hide_comments"
              checked={this.state.hide_comments}
              onChange={(event, data) => {
                this.handleChange(event, { value: data.checked, ...data });
              }}
            />
          </Form.Field>
        ) : null}
        <Button
          type="submit"
          primary={true}
          loading={this.state.saving}
          onClick={() => {
            this.setState({ saving: true }, () => {
              window.setTimeout(() => {
                if (!this.dismounted) {
                  this.setState({ saving: false });
                }
              }, 2000);
            });
          }}
        >
          Save Changes
        </Button>
      </Form>
    );
  }
}

class TuiEditor extends React.PureComponent {
  componentDidMount() {
    this.editor = new Editor({
      el: document.querySelector('#editText'),
      initialEditType: 'markdown',
      previewStyle: 'vertical',
      height: '800px',
      usageStatistics: false,
      initialValue: this.props.initial,
      exts: ['scrollSync', 'table'],
      events: {
        change: () => {
          this.props.onChange(this.editor.getMarkdown());
        },
        blur: () => {
          this.props.onBlur();
        }
      }
    });
  }
  render() {
    return <div id="editText" />;
  }
}

class PreviewBlogitem extends React.PureComponent {
  render() {
    const { data } = this.props;
    if (!data) {
      return null;
    }
    return (
      <div className="preview">
        <h3>PREVIEW</h3>
        <div
          dangerouslySetInnerHTML={{
            __html: data.html
          }}
        />
      </div>
    );
  }
}

class Thumbnails extends React.PureComponent {
  state = { copied: null, show: false, images: null };

  async componentDidMount() {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.oid;
    try {
      const response = await fetch(`/api/v0/plog/${oid}/images`, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
      this.setState({ loading: false });
      if (response.ok) {
        const json = await response.json();
        this.setState({ images: json.images });
      } else {
        this.setState({ serverError: response }, () => {
          window.scrollTo(0, 0);
        });
      }
    } catch (ex) {
      this.setState({ serverError: ex }, () => {
        window.scrollTo(0, 0);
      });
    }
  }
  setCopied = key => {
    this.setState({ copied: key }, () => {
      if (this.timeout) {
        window.clearTimeout(this.timeout);
      }
      this.timeout = window.setTimeout(() => {
        if (!this.dismounted) {
          this.setState({ copied: false });
        }
      }, 3000);
    });
  };
  render() {
    if (!this.state.show && !this.state.images) {
      return null;
    }
    if (!this.state.show && this.state.images) {
      if (!this.state.images.length) {
        return null;
      }
      return (
        <Button
          onClick={event => {
            this.setState({ show: true });
          }}
        >
          Show ({this.state.images.length}) thumbnails
        </Button>
      );
    }
    const { images } = this.state;
    const keys = ['small', 'big', 'bigger'];
    return (
      <div>
        <Button
          onClick={event => {
            this.setState({ show: false });
          }}
        >
          Hide thumbnails
        </Button>
        {images.map(image => {
          return (
            <Card.Group key={image.full_url}>
              {keys.map(key => {
                const thumb = image[key];

                const imageTagHtml = `
                <img src="${thumb.url}" alt="${thumb.alt}" width="${thumb.width}" height="${thumb.height}">
                `.trim();
                const aTagHtml = `
                <a href="${image.full_url}">${imageTagHtml.replace(
                  'width=',
                  'class="floatright" width='
                )}</a>
                `.trim();
                return (
                  <Card key={key}>
                    <a href={BASE_URL + thumb.url}>
                      <Image src={BASE_URL + thumb.url} />
                    </a>
                    <Card.Content>
                      <Card.Header>{key}</Card.Header>
                      <Card.Meta>
                        <span className="date">{`${thumb.width}x${thumb.height}`}</span>
                      </Card.Meta>
                      <Card.Description>{thumb.alt}</Card.Description>
                      {this.state.copied === key ? (
                        <small>copied!</small>
                      ) : null}
                    </Card.Content>
                    <Card.Content extra>
                      <Icon name="copy" loading={this.state.copied === key} />
                      <CopyToClipboard
                        text={thumb.url}
                        onCopy={() => this.setCopied(key)}
                      >
                        <Button size="mini">URL</Button>
                      </CopyToClipboard>
                      <CopyToClipboard
                        text={imageTagHtml}
                        onCopy={() => this.setCopied(key)}
                      >
                        <Button size="mini">Image tag</Button>
                      </CopyToClipboard>
                      <CopyToClipboard
                        text={aTagHtml}
                        onCopy={() => this.setCopied(key)}
                      >
                        <Button size="mini">Whole tag</Button>
                      </CopyToClipboard>
                    </Card.Content>
                  </Card>
                );
              })}
            </Card.Group>
          );
        })}
      </div>
    );
  }
}

class BlogitemHits extends React.PureComponent {
  state = {
    hits: null,
    serverError: null
  };
  componentDidMount() {
    // Delay a bit because it's not critical
    setTimeout(this.fetchHits, 2000);
  }
  componentWillUnmount() {
    this.dismounted = true;
  }
  fetchHits = async () => {
    const { blogitem } = this.props;
    try {
      const response = await fetch(`/api/v0/plog/${blogitem.oid}/hits`, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
      if (response.ok) {
        const json = await response.json();
        this.setState({
          serverError: null,
          hits: json.hits
        });
      } else {
        this.setState({ serverError: response });
      }
    } catch (ex) {
      this.setState({ serverError: ex });
    }
  };
  render() {
    if (this.state.serverError)
      return <ShowServerError error={this.state.serverError} />;
    const { hits } = this.state;
    if (!hits) return null;
    return (
      <div style={{ marginTop: 100 }}>
        <Divider />
        <h3>Hits</h3>
        <Statistic.Group widths="four">
          {hits.map(hit => {
            return (
              <Statistic key={hit.key}>
                <Statistic.Value>{hit.value.toLocaleString()}</Statistic.Value>
                <Statistic.Label>{hit.label}</Statistic.Label>
              </Statistic>
            );
          })}
        </Statistic.Group>
      </div>
    );
  }
}

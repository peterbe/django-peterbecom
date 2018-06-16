import {
  action,
  extendObservable,
  ObservableMap,
  configure,
  runInAction
} from 'mobx';
import { getTime, isBefore } from 'date-fns/esm';

configure({ enforceActions: true });

function escapeRegExp(s) {
  return s.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
}

const blogitemsListToObject = list => {
  return list.reduce((result, item) => {
    item._modify_ts = getTime(item.modify_date);
    item._is_published = isBefore(item.pub_date, new Date());
    result[item.id] = item;
    return result;
  }, {});
};

class BlogitemStore {
  constructor(rootStore) {
    this.rootStore = rootStore;

    extendObservable(this, {
      // blogitems: JSON.parse(localStorage.getItem('blogitems') || '{}'),
      blogitems: new ObservableMap(
        JSON.parse(localStorage.getItem('blogitems') || '{}')
      ),
      // setBlogitems: action(blogitems)
      latestBlogitemDate: localStorage.getItem('latestBlogitemDate') || null,
      // latestBlogitemDate: null,
      categories: [],
      _persist: action(() => {
        localStorage.setItem('blogitems', JSON.stringify(this.blogitems));
        localStorage.setItem('latestBlogitemDate', this.latestBlogitemDate);
      }),
      _setlatestBlogitemDate: action(() => {
        let date, ts;
        for (let item of this.blogitems.values()) {
          if (!date || item._modify_ts > ts) {
            date = item.modify_date;
            ts = item._modify_ts;
          }
        }
        this.latestBlogitemDate = date;
      }),
      loaded: false,
      serverError: null,
      updateBlogitems: action(async () => {
        let url = '/api/v1/blogitems/';
        url += `?since=${this.latestBlogitemDate}`;
        const response = await fetch(url);
        if (response.ok) {
          const data = await response.json();
          runInAction(() => {
            console.log(
              data.blogitems.count,
              'Updates since',
              data.latest_blogitem_date
            );
            this.blogitems.merge(blogitemsListToObject(data.blogitems.results));
            this.filterBlogitems();
            this._setlatestBlogitemDate();
            if (data.blogitems.next) {
              throw new Error(`DEAL WITH ${data.blogitems.next}`);
            }
            this._persist();
            this.serverError = null;
            this.loaded = true;
          });
        } else {
          runInAction(() => {
            this.serverError = response.status;
            this.loaded = true;
          });
        }
      }),
      fetchBlogitems: action(async (url = null) => {
        const response = await fetch(url || '/api/v1/blogitems/');
        if (response.ok) {
          const data = await response.json();
          runInAction(() => {
            console.log(`Fetched ${data.blogitems.results.length} items`);
            this.blogitems.merge(blogitemsListToObject(data.blogitems.results));
            if (data.blogitems.next) {
              this.fetchBlogitems(
                data.blogitems.next.replace('http://localhost:8000', '')
              );
            } else {
              this.filterBlogitems();
              this._setlatestBlogitemDate();
              this._persist();
              this.serverError = null;
              this.loaded = true;
            }
          });
        } else {
          runInAction(() => {
            this.serverError = response.status;
            this.loaded = true;
          });
        }
      }),
      filters: {
        categories: [],
        search: ''
      },
      activePage: 1,
      setActivePage: action(page => {
        this.activePage = page;
      }),
      pageBatchSize: 10,
      filteredCount: 0,
      resetFilters: action(() => {
        this.filters = {
          categories: [],
          search: ''
        };
        this.activePage = 1;
        this.filterBlogitems();
      }),
      setFilters: action(filters => {
        this.filters = filters;
        this.activePage = 1;
        this.filterBlogitems();
      }),
      filterBlogitems: action(() => {
        let searchRegex = null;
        if (this.filters.search) {
          searchRegex = new RegExp(escapeRegExp(this.filters.search), 'i');
        }
        // Remember, this.blogitems is an ObservableMap and
        // this.blogitems.values() is an Iterator.
        const filtered = Array.from(this.blogitems.values()).filter(item => {
          if (searchRegex) {
            if (!(searchRegex.test(item.title) || searchRegex.test(item.oid))) {
              return false;
            }
          }
          if (this.filters.categories.length) {
            if (
              !item.categories.find(category => {
                return this.filters.categories.includes(category.name);
              })
            ) {
              return false;
            }
          }
          return true;
        });
        filtered.sort((a, b) => b._modify_ts - a._modify_ts);
        this.filtered = filtered;
        this.filteredCount = filtered.length;
      }),
      filtered: [],
      get pageFiltered() {
        // return this.filtered
        //   .sort((a, b) => b._modify_ts - a._modify_ts)
        //   .slice(
        //     (this.activePage - 1) * this.pageBatchSize,
        //     this.activePage * this.pageBatchSize
        //   );
        return this.filtered.slice(
          (this.activePage - 1) * this.pageBatchSize,
          this.activePage * this.pageBatchSize
        );
      },
      blogitem: null,
      fetchBlogitem: async (id, accessToken) => {
        if (!accessToken) {
          throw new Error('No accessToken');
        }
        const response = await fetch(`/api/v1/blogitems/${id}/`, {
          headers: {
            Authorization: `Bearer ${accessToken}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          runInAction(() => {
            this.blogitem = data.blogitem;
            this.serverError = null;
            this.loaded = true;
          });
        } else {
          runInAction(() => {
            this.serverError = response.status;
            this.loaded = true;
          });
        }
      },
      updated: null,
      setUpdated: action(updated => {
        this.updated = updated;
      }),
      updateBlogitem: async (id, data, accessToken) => {
        if (!accessToken) {
          throw new Error('No accessToken');
        }
        const response = await fetch(`/api/v1/blogitems/${id}/`, {
          method: 'PUT',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`
          },
          body: JSON.stringify(data)
        });
        if (response.ok) {
          const data = await response.json();
          runInAction(() => {
            console.log('RESULT', data);
            this.blogitem = data.blogitem;
            this.updated = new Date();
          });
        } else {
          runInAction(() => {
            this.serverError = response.status;
          });
        }
      },
      // setBlogitem: action(blogitem => {
      //   this.blogitem = blogitem;
      // }),
      allCategories: [],
      setAllCategories: action(
        allCategories => (this.allCategories = allCategories)
      ),
      fetchAllCategories: () => {
        fetch('/api/v1/categories/')
          .then(r => r.json())
          .then(categories => this.setAllCategories(categories));
      }
    });
  }
}

class UserStore {
  constructor(rootStore) {
    this.rootStore = rootStore;
    extendObservable(this, {
      accessToken: null,
      setAccessToken: action(accessToken => {
        this.accessToken = accessToken;
      }),
      userInfo: null,
      setUserInfo: action(userInfo => {
        this.userInfo = userInfo;
      }),
      serverError: null,
      setServerError: action(serverError => {
        this.serverError = serverError;
      })
    });
  }
}

class RootStore {
  constructor() {
    this.user = new UserStore(this);
    this.blogitems = new BlogitemStore(this);
  }
}
// import { decorate, observable } from "mobx"

const store = (window.store = new RootStore());
// const store = (window.store = new TodoStore());

export default store;

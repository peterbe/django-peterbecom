// See https://github.com/preactjs/preact-cli/wiki/Config-Recipes

export default (config, env, helpers) => {
  // console.log("CONFIG");
  // config.template = "template.html";
  // console.warn(config);
  // console.log("----------------");

  // Always only for the browser. No SSR.
  env.prerender = false; // XXX DOESN'T WORK
  env.ssr = false; // XXX not sure what this does.
  // env.template = "template.html";
  // console.log("ENV");
  // console.log(env);
  // Because that's what the songsearch CORS this requires.
  // The conditional check is because `preact build` doesn't
  // have a devServer.
  if (config.devServer) {
    config.devServer.port = "3000";
    // console.log(config.devServer);
  }
};

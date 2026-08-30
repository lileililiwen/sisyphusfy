#!/usr/bin/env node
"use strict";

const { launch } = require("../lib/launcher.js");

launch(process.argv.slice(2)).catch((err) => {
  console.error(err.message);
  process.exit(1);
});

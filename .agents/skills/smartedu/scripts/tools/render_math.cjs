const fs=require('fs');
const katex=require('../vendor/katex/katex.min.js');
const expressions=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(expressions.map(e=>katex.renderToString(e.latex,{output:'mathml',displayMode:e.block,throwOnError:true,trust:false,strict:'error',maxExpand:1000,maxSize:20}))));

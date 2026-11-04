import test from 'node:test';
import assert from 'node:assert/strict';

import { sanitizeSegment, buildFilename, dateParts } from '../src/lib/filename.js';

const date = new Date(2026, 10, 4, 14, 5, 9); // 2026-11-04 14:05:09 lokal tid

test('sanitizeSegment rensar otillåtna tecken', () => {
  assert.equal(sanitizeSegment('Hej: världen?/ja*'), 'Hej- världen-ja');
  assert.equal(sanitizeSegment('   '), 'sida');
  assert.equal(sanitizeSegment('...fil...'), 'fil');
  assert.equal(sanitizeSegment(''), 'sida');
  assert.equal(sanitizeSegment('CON'), '_CON');
  assert.equal(sanitizeSegment('en', 1), 'e');
});

test('dateParts formaterar lokal tid', () => {
  assert.deepEqual(dateParts(date), {
    date: '2026-11-04',
    time: '14-05-09',
    year: '2026',
    month: '11',
    day: '04'
  });
});

test('buildFilename bygger mapp och filnamn', () => {
  assert.equal(
    buildFilename({
      template: '{date}_{title}',
      folder: 'Sidor',
      perSiteFolder: true,
      site: 'example.com',
      title: 'Nyheter idag',
      date
    }),
    'Sidor/example.com/2026-11-04_Nyheter idag.pdf'
  );
});

test('buildFilename klarar tom mall, tom mapp och utan sajtmapp', () => {
  assert.equal(
    buildFilename({
      template: '',
      folder: '',
      perSiteFolder: false,
      site: 'example.com',
      title: 'Sida',
      date
    }),
    '2026-11-04_Sida.pdf'
  );
});

test('buildFilename ersätter okända taggar och städar filnamn', () => {
  const name = buildFilename({
    template: '{site}/{title} ({okand})',
    folder: 'PDF',
    perSiteFolder: false,
    site: 'www.example.com',
    title: 'A/B: test?',
    date
  });
  assert.equal(name, 'PDF/www.example.com-A-B- test.pdf');
  assert.ok(!name.includes('{'), 'inga taggar ska vara kvar');
});

test('buildFilename lägger bara till .pdf en gång', () => {
  const name = buildFilename({
    template: 'rapport.pdf',
    folder: '',
    perSiteFolder: false,
    site: 'example.com',
    title: 'x',
    date
  });
  assert.equal(name, 'rapport.pdf');
});

test('buildFilename begränsar långa titlar', () => {
  const longTitle = 'a'.repeat(300);
  const name = buildFilename({
    template: '{title}',
    folder: 'Sidor',
    perSiteFolder: true,
    site: 'example.com',
    title: longTitle,
    date
  });
  const fileName = name.split('/').pop();
  assert.ok(fileName.length <= 125, `filnamnet var ${fileName.length} tecken`);
  assert.ok(fileName.endsWith('.pdf'));
});

test('buildFilename använder alla taggar', () => {
  const name = buildFilename({
    template: '{year}-{month}-{day}_{time}_{site}',
    folder: 'S',
    perSiteFolder: false,
    site: 'example.com',
    title: 'x',
    date
  });
  assert.equal(name, 'S/2026-11-04_14-05-09_example.com.pdf');
});

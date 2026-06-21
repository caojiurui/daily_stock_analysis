import { describe, expect, test } from 'vitest';
import { searchStocks } from '../searchStocks';
import type { StockIndexItem } from '../../types/stockIndex';

const index: StockIndexItem[] = [
  {
    canonicalCode: '510300.SH',
    displayCode: '510300',
    nameZh: '沪深300ETF',
    pinyinFull: 'hushen300etf',
    pinyinAbbr: 'hs300etf',
    aliases: ['300etf'],
    market: 'CN',
    assetType: 'etf',
    active: true,
    popularity: 90,
  },
  {
    canonicalCode: '000300.SH',
    displayCode: '000300',
    nameZh: '沪深300',
    pinyinFull: 'hushen300',
    pinyinAbbr: 'hs300',
    aliases: ['hs300'],
    market: 'INDEX',
    assetType: 'index',
    active: true,
    popularity: 88,
  },
];

describe('searchStocks asset type support', () => {
  test('returns asset type metadata in suggestions', () => {
    const results = searchStocks('沪深300ETF', index);
    expect(results[0].canonicalCode).toBe('510300.SH');
    expect(results[0].assetType).toBe('etf');
  });

  test('supports restricting search by asset type', () => {
    const results = searchStocks('沪深300', index, { assetTypes: ['index'] });
    expect(results.length).toBeGreaterThan(0);
    expect(results.every((item) => item.assetType === 'index')).toBe(true);
  });
});

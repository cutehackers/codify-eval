import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/api.dart';
import 'package:fixture_app/pricing.dart';
import 'package:fixture_app/reservations.dart';
void main(){
 test('aggregate discount rounding and after-discount shipping',(){
  final q=quote([const Line('a',1,3333),const Line('a',1,2100)],member:true,region:'mainland');expect(q.subtotalCents,5433);expect(q.discountCents,407);expect(q.shippingCents,0);expect(q.totalCents,5026);
  final under=quote([const Line('a',1,5405)],member:true,region:'island');expect(under.discountCents,405);expect(under.shippingCents,300);
  final below=quote([const Line('a',1,5404)],member:true,region:'island');expect(below.shippingCents,800);
  final tiny=quote([const Line('a',1,7),const Line('b',1,7)],member:true,region:'mainland');expect(tiny.discountCents,1);
  expect(quote([],member:true,region:'island').totalCents,0);
 });
 test('pricing rejects invalid contract inputs and leaves input intact',(){
  expect(()=>quote([],member:false,region:'other'),throwsArgumentError);
  for(final line in [const Line(' ',1,1),const Line('a',0,1),const Line('a',-1,1),const Line('a',1,-1)]) {expect(()=>quote([line],member:false,region:'mainland'),throwsArgumentError);}
  final lines=[const Line('a',2,3000)];quote(lines,member:false,region:'island');expect(lines.single.quantity,2);expect(quote(lines,member:false,region:'island').shippingCents,300);
 });
 test('aggregate reservations reject atomically and preserve maps',(){
  final stock={'a':3,'b':2,'zero':0};final lines=[const Line('a',2,100),const Line('a',2,100),const Line('b',1,100)];final r=reserve(stock,lines);
  expect(r.accepted,false);expect(r.available,stock);expect(r.requested,{'a':4,'b':1});expect(stock,{'a':3,'b':2,'zero':0});expect(()=>r.available['a']=9,throwsUnsupportedError);expect(()=>r.requested.clear(),throwsUnsupportedError);
  final missing=reserve(stock,[const Line('unknown',1,0)]);expect(missing.accepted,false);expect(missing.available.containsKey('unknown'),false);
 });
 test('accepted and empty reservations are immutable snapshots',(){
  final stock={'a':3,'b':2};final r=reserve(stock,[const Line('a',1,100),const Line('a',2,0)]);expect(r.accepted,true);expect(r.available,{'a':0,'b':2});expect(r.requested,{'a':3});expect(stock['a'],3);
  stock['b']=99;expect(r.available['b'],2);final empty=reserve({'a':0},[]);expect(empty.accepted,true);expect(empty.available,{'a':0});expect(empty.requested,isEmpty);
 });
 test('reservation validates full input before any deductions',(){
  for(final line in [const Line(' ',1,1),const Line('a',0,1),const Line('a',1,-1)]){expect(()=>reserve({'a':5},[line]),throwsArgumentError);}
  expect(()=>reserve({'a':-1},[]),throwsArgumentError);expect(()=>reserve({' ':1},[]),throwsArgumentError);
 });
 test('nonmember policy is explicit and snapshots survive input changes',(){
  final q=quote([const Line('a',2,3333)],member:false,region:'mainland');expect(q.discountCents,0);expect(q.subtotalCents,6666);expect(q.shippingCents,0);expect(q.totalCents,6666);
  final stock={'a':4};final lines=[const Line('a',2,5)];final r=reserve(stock,lines);lines[0]=const Line('b',9,0);stock['a']=99;expect(r.requested,{'a':2});expect(r.available,{'a':2});expect(()=>r.available.clear(),throwsUnsupportedError);expect(()=>r.requested['b']=1,throwsUnsupportedError);
 });
 test('later invalid lines and negative requests reject without mutating inputs',(){
  for(final bad in [const Line('a',-1,1),const Line(' ',1,1),const Line('a',0,1),const Line('a',1,-1)]) {
   final stock={'a':5};final lines=[const Line('a',1,10),bad];expect(()=>reserve(stock,lines),throwsArgumentError);expect(stock,{'a':5});expect(lines.first.quantity,1);expect(()=>quote(lines,member:true,region:'mainland'),throwsArgumentError);
  }
 });

}

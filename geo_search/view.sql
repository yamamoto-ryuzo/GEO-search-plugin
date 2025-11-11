DROP VIEW IF EXISTS public."地籍_地籍Search";CREATE
OR REPLACE VIEW public."地籍_地籍Search" AS
SELECT
    "コード表_字"."字" :: text || "地籍_マルコポーロ".tiban :: text AS "住所",
    "地籍_マルコポーロ".kanjname as "漢字氏名",
    "地籍_マルコポーロ".kananame as "カナ氏名",
    "コード表_地目（登記）"."地目（登記）",
    "地籍_マルコポーロ".tiseki1 as "地籍",
    "コード表_地目（現況）"."地目（現況）",
    "地籍_マルコポーロ".jyusho,
    "地籍_マルコポーロ".ogc_fid,
    "地籍_マルコポーロ".wkb_geometry,
    "地籍_マルコポーロ".scale,
    "地籍_マルコポーロ".azacd :: integer as "字CD",
    "地籍_マルコポーロ".ownercd as "所有者CD",
    "コード表_字"."字",
    "地籍_マルコポーロ".tiban as "地番",
    SPLIT_PART("地籍_マルコポーロ".tiban, '-', 1) as "地番-本番",
    SPLIT_PART("地籍_マルコポーロ".tiban, '-', 2) as "地番-枝番",
    SPLIT_PART("地籍_マルコポーロ".tiban, '-', 3) as "地番-孫",
    SPLIT_PART("地籍_マルコポーロ".tiban, '-', 4) as "地番-判"
FROM
    "地籍_マルコポーロ",
    "コード表_字",
    "コード表_地目（現況）",
    "コード表_地目（登記）"
WHERE
    "地籍_マルコポーロ".azacd = "コード表_字"."字コード" :: numeric
    AND "地籍_マルコポーロ".timoku1 = "コード表_地目（登記）"."地目（登記）コード" :: numeric
    AND "地籍_マルコポーロ".timoku2 = "コード表_地目（現況）"."地目（現況）コード" :: numeric;
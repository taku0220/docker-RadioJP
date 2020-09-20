# docker-RadioJP

This program is only available in Japan and not in other countries.  

ラジコとらじる★らじるをforked-daapdで聴けるようにする中継アプリです。  
私的利用の範囲で使用してください。  

テスト環境: TS-231P(QNAP NAS)のContainer Station  
　+forked-daapd version 27.1+patch[(taku0220/docker-daapd-patcher)](https://github.com/taku0220/docker-daapd-patcher)  
　+Remote app(iPhone)  
x86-64とarm64のArchitectureについてはまだテストしてません。  

同一PC(server)内での連携を想定してます。  
他のPC(server)内のforked-daapdと連携する場合は設定で変更が出来ますがセキュリティに注意してください。  

## インストール
Architectureがarmhfの場合でのコマンドになります。  
インストールの基本については下記を参考にしています。  
[How To: Setup Containers on QNAP - LinuxServer.io](https://blog.linuxserver.io/2017/09/17/how-to-setup-containers-on-qnap/)

Docker Hubにはライセンスを満たせませんのでアップロードしません。(バイナリに該当すると思われるのでイメージ内の全てのソフトウェアライセンスに沿った対応、管理は難しい。)  
下記手順は自前でDockerイメージをビルドする方法になります。  

### ダウンロード
**1.適当なフォルダに移動後、ダウンロードします。**  
`/path/to`は適当なフォルダという意味合いで使用しています。  
gitコマンドが使える場合は`git clone`してください。  
```bash
cd /path/to

curl -o docker-RadioJP.tar.gz \
-L "https://github.com/taku0220/docker-RadioJP/archive/master.tar.gz"
```
**2.展開先のフォルダを作成。**  
```bash
mkdir docker-RadioJP
```
**3.build用データを展開する。**  
`docker-RadioJP`フォルダにファイルが展開されます。  
```bash
tar xf docker-RadioJP.tar.gz -C docker-RadioJP --strip-components=1
```
**4.`docker-RadioJP`フォルダに移動します。**  
```bash
cd docker-RadioJP
```

### イメージのbuild  
**1.build**  
```bash
docker build -f Dockerfile.armhf --no-cache=true -t docker-radiojp:1.0 .
```  
**2.ビルドステージの削除**  
ビルドした後、不要になったデーターが残る場合があるので下記コマンドにて掃除してください。  
削除されるのは未使用状態のデータのみです。  
```bash
docker image prune
```
`Are you sure you want to continue? [y/N]`と聞かれるので削除してよければ、`y` を入力後 `Enter`で決定してください。  

### コンテナの作成  
**1.コンテナに割り当てるユーザーのuid、gidの確認**  
idコマンドで確認します。(例: `dockuser`の場合)  
```bash
id dockuser
```
コマンド表示例  
```
[~] # id dockuser
uid=501(dockuser) gid=100(everyone)
```
**2.config用のフォルダ作成**  
configフォルダはdocker外から操作出来る所に作成してください。
```bash
mkdir /path/to/config
```
**3.コンテナの作成**  
```bash
docker create \
--name=docker-RadioJP \
-v /path/to/config:/config \
-e PUID=501 -e PGID=100 -e TZ=Asia/Tokyo \
--log-opt max-size=10m --log-opt max-file=3 \
--net=host \
docker-radiojp:1.0
```
|行数 |パラメータ|内容                                   |
|:---:|:-------:|--------------------------------------|
|2行目|`--name`|作成するコンテナの名前（任意に変更可）。|
|3行目|`-v`|共有フォルダーの設定、コンテナとPC間でのデータ共有用<br>書式 : -v PC側フォルダ:コンテナ側フォルダ<br><br>`3行目` : docker-RadioJPの設定、Log、他用|
|4行目|`-e`|環境変数<br><br>`PUID` : ユーザーID(PC側ユーザーの`uid`)<br>`PGID` : グループID(PC側ユーザーの`gid`)<br>`TZ` : タイムゾーン|
|5行目|`--log-opt`|docker logging設定(ログローテーション)<br><br>`max-size` : logの最大サイズ<br>`max-file` : 残す世代数|
|6行目|`--net`|ネットワークモード|
|7行目| |コンテナの元にするイメージ名:バージョン|

## 起動
- コンテナ起動コマンド  
```bash
docker start docker-RadioJP
```
- コンテナ停止コマンド  
```bash
docker stop docker-RadioJP
```
初回起動時もしくは`/config`に設定ファイルの`general_config.conf`が無い場合は`general_config.conf`を作成後にコンテナは強制的に停止します。  
設定を確認後に再度コンテナ起動コマンドを実行してください。  

## 設定
- general_config.conf
    |項目 |内容                           |
    |:---:|------------------------------|
    ||**- icecast config -**|
    |ice_url|icecast url and port|
    |ice_mount|icecast mount point name|
    |ice_pass|icecast password|
    |ice_loglevel|icecast loglevel|
    ||**- app web server config -**|
    |HOST|Flaskのlisten(待ち受け)設定<br>"": localhost(127.0.0.1)のみ<br>"0.0.0.0": Lan内に公開|
    |PORT|Flaskのport|
    |DEBUG|Flaskのdebug mode|
    ||**- app config -**|
    |format|オーディオ出力のフォーマット "AAC"か"MP3"|
    |my_headers|icecastのlog判別用|
    |ice_ping|icecast 死活監視インターバル|
    |tmp_limit|/tmpに保存されたイレギュラーartworkファイル削除用、<br>24時間間隔でチェックし未使用時間経過ファイルは削除する。|
    |chunk_size|output 調整用|
    |artwork_ip|イレギュラーartworkファイルへのリンク用|
    |playlist_url|playlist自動作成用。Flaskへのurl(option)|
    |radiko_volume|音量（微調整用）MP3の時のみ|
    |radiru_volume|音量（微調整用）MP3の時のみ|
    |radiko_delay|番組情報の更新タイミングを遅延させる時間。|
    |radiru_delay|番組情報の更新タイミングを遅延させる時間。|

- logging_config.conf  
    Python標準のloggingを使用しています。詳細は下記を参照してください。  
    [ロギングの環境設定(環境設定辞書スキーマ) - Python Docs](https://docs.python.org/ja/3/library/logging.config.html#logging-config-dictschema)

### forked-daapd patch
hederにて放送局名を通知しますが日本語(utf-8)の場合、文字化けしてしまいます。  
RFCとか調べ切れてませんが暫定的にパッチにて対応します。  
このリポジトリ内の`forked-daapd_patch`フォルダにパッチがありますのでプレイリストをforked-daapdに認識させる前にパッチを適用してください。

### プレイリスト  
下記コマンドを実行する事で`/config/playlist`に作成されます。  
```bash
docker exec -it docker-RadioJP python3 /radio/app/radio_playlist.py
```
`Radiko.m3u`と`Radiru.m3u`及び個別に放送局ごとのm3uファイルが作成されます。
forked-daapdのindexディレクトリ(デフォルトは"/srv/music")に追加すると１局ごとテスト接続が行われます。  
forked-daapdの起動時も同様に接続テストが行われるので起動完了まで時間がかかる場合があります。

登録されたプレイリストはRemote appの`インターネットラジオ`から見れます。再生開始には５秒程度かかります。

### etc  
 - Flaskは開発用サーバーです。インターネットへの公開等を前提に作られていません。(テスト用という事だと思います。)  
 - forked-daapdはポーズ(一時停止)後の再スタートをスムーズに行うため一旦接続を切断後、再度接続し待機する仕様です。  
ポーズと再生が判別出来ない為、同一のリクエストが連続した場合をポーズとして認識させ再生を停止させるようにしています。  
 - 一部artworkの拡張子が\*.jpegと\*.gifがあり、forked-daapdは \*.jpgと\*.pngしか受け付けない為、`/tmp/artwork`に保存しイレギュラー用のURLをアナウンスします。  
 - ラジコの番組データを使わせて頂いております。その関係上一部の放送局は取得出来ない場合があります。  
   取得出来なかった場合artworkは`/config/artwork_option`内に`station_id.jpg`をいれておくとそのURLをアナウンスさせる事が可能です。  
 - 原因が特定出来ていないが数時間で再生が止まってしまう事がある。

## ライセンス

このプログラムはフリーソフトウェアです。 Free Software Foundationが発行するGNU General Public License(ライセンスのバージョン3、または（オプションで）以降のバージョン)の条件に基づいて、再配布または変更、あるいはその両方を行うことができます。

このプログラムは、役立つことを期待して配布されていますが、いかなる保証もありません。  
商品性または特定の目的への適合性の暗黙の保証さえありません。  
詳細については、GNU General Public Licenseを参照してください。

このプログラムとともに、GNU General Public Licenseのコピーを受け取っているはずです。  
そうでない場合は、http://www.gnu.org/licenses/ を参照してください。

各パッチファイルは異なるライセンスが適用されています。
フォルダ内のREADME.mdを参照してください。


## Acknowledgments / 謝辞
下記を参考にさせて頂きました。
Thanks to them.
 - [takuya/play-radiko](https://github.com/takuya/play-radiko)
 - [river24/icecadiko](https://github.com/river24/icecadiko)
 - [pallets/flask](https://github.com/pallets/flask)
 - [ejurgensen/forked-daapd](https://github.com/ejurgensen/forked-daapd)
 - [xiph/icecast-server](https://gitlab.xiph.org/xiph/icecast-server)
 - [xiph/icecast-libshout](https://gitlab.xiph.org/xiph/icecast-libshout)  
 - [codders/libshout](https://github.com/codders/libshout) (Shoutcast library with AAC support)
 - [xiph/ezstream](https://gitlab.xiph.org/xiph/ezstream)

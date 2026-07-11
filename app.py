import io
import zipfile
import github
from github import Github
import streamlit as st

# --- ページの設定 ---
st.set_page_config(page_title="ZIP to GitHub Sync", page_icon="🔄", layout="centered")

st.title("🔄 ZIP-to-GitHub 完全同期ツール")
st.write("アップロードされたZIPファイルを解凍し、GitHubリポジトリの中身を完全に一致（古いファイルは自動削除）させます。")

# --- 画面の入力フォーム作成（設定情報） ---
st.sidebar.header("🔑 設定情報")

if "GITHUB_TOKEN" in st.secrets:
    ACCESS_TOKEN = st.secrets["GITHUB_TOKEN"]
    st.sidebar.success("✅ トークンはSecretsから自動読み込み中")
else:
    ACCESS_TOKEN = st.sidebar.text_input(
        "GitHub Access Token", type="password", help="ghp_から始まるトークン"
    )

REPO_NAME = st.sidebar.text_input(
    "Repository", 
    value="rioki3/surveycad", 
    placeholder="ユーザー名/リポジトリ名"
)
BRANCH_NAME = st.sidebar.text_input("Branch", value="main")

# --- メイン画面：ファイルアップロード ---
uploaded_file = st.file_uploader(
    "1. テスト対象のZIPファイルをドロップしてください", type=["zip"]
)


def get_all_github_files(repo, branch, path=""):
    """GitHubリポジトリ内のすべてのファイルパスを再帰的に取得する関数"""
    file_list = []
    try:
        contents = repo.get_contents(path, ref=branch)
        if not isinstance(contents, list):
            contents = [contents]
        
        for content in contents:
            if content.type == "dir":
                file_list.extend(get_all_github_files(repo, branch, content.path))
            else:
                file_list.append(content.path)
    except github.UnknownObjectException:
        pass
    return file_list


# --- 同期処理の関数 ---
def process_and_sync(uploaded_file, token, repo_name, branch):
    g = Github(token)
    try:
        repo = g.get_repo(repo_name)
    except Exception as e:
        st.error(f"⚠️ GitHubリポジトリへの接続に失敗しました。リポジトリ名やトークンの設定、または全角スペースや日本語が混ざっていないか確認してください。\n\n詳細エラー: {e}")
        return False

    st.text("🔍 GitHub上の既存ファイルを調査中...")
    github_files_before = get_all_github_files(repo, branch)
    zip_files = set()

    zip_buffer = io.BytesIO(uploaded_file.read())
    with zipfile.ZipFile(zip_buffer, "r") as z:
        for file_path in z.namelist():
            if (
                file_path.endswith("/")
                or "__MACOSX" in file_path
                or ".DS_Store" in file_path
            ):
                continue

            zip_files.add(file_path)

            with z.open(file_path) as f:
                raw_data = f.read()
                try:
                    file_content = raw_data.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        file_content = raw_data.decode("cp932")
                    except UnicodeDecodeError:
                        st.warning(f"⚠️ テキスト（UTF-8/Shift-JIS）ではないためスキップ: {file_path}")
                        continue

            commit_message = f"Update {file_path} via Web Sync Tool"

            try:
                # GitHub上の既存ファイルのメタデータを取得
                contents = repo.get_contents(file_path, ref=branch)
                if isinstance(contents, list):
                    st.warning(f"⚠️ GitHub上の同名パスがフォルダです（上書きスキップ）: {file_path}")
                    continue

                # 💡 巨大ファイルの比較エラー対策：
                # 既存の中身をデコードして比較することを試みるが、
                # もし失敗するか巨大すぎる場合は、比較をスキップして「強制上書き」する
                try:
                    existing_text = contents.decoded_content.decode("utf-8")
                    if existing_text == file_content:
                        st.text(f"➖ 変更なし（スキップ）: {file_path}")
                        continue
                except Exception:
                    st.text(f"🔄 巨大ファイルまたは解析不可のため強制上書きを選択: {file_path}")

                # 更新処理の実行
                repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=file_content,
                    sha=contents.sha,
                    branch=branch,
                )
                st.success(f"✏️ 更新完了: {file_path}")

            except github.UnknownObjectException:
                # GitHub側にまだ存在しないファイルは新規作成
                repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=file_content,
                    branch=branch,
                )
                st.info(f"🆕 新規追加: {file_path}")
            except Exception as e:
                st.error(f"❌ 処理中にエラーが発生しました ({file_path}): {e}")

    # 自動削除
    st.text("🗑️ 古いファイルの削除チェック中...")
    for old_file in github_files_before:
        if old_file not in zip_files:
            try:
                contents = repo.get_contents(old_file, ref=branch)
                repo.delete_file(
                    path=old_file,
                    message=f"Delete {old_file} (Not found in latest ZIP)",
                    sha=contents.sha,
                    branch=branch
                )
                st.error(f"🗑️ 古いファイルを削除しました: {old_file}")
            except Exception as e:
                st.warning(f"⚠️ ファイルの削除に失敗しました ({old_file}): {e}")

    return True


# --- 2. 実行ボタン ---
if uploaded_file:
    if st.button("🚀 GitHubのコードを最新状態に完全交換する", use_container_width=True):
        if not ACCESS_TOKEN or not REPO_NAME:
            st.error("アクセストークンとリポジトリ名が設定されていません。")
        else:
            with st.spinner("GitHubと完全同期中..."):
                success = process_and_sync(uploaded_file, ACCESS_TOKEN, REPO_NAME, BRANCH_NAME)
            
            if success:
                st.balloons()  
                st.success("すべての同期・クリーンアップ処理が完了しました！")
            else:
                st.error("同期処理は中断されました。上記のエラーを確認してください。")

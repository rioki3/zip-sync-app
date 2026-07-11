import io
import zipfile
import github
from github import Github
import streamlit as st

# --- ページの設定 ---
st.set_page_config(page_title="ZIP to GitHub Sync", page_icon="🔄", layout="centered")

st.title("🔄 ZIP-to-GitHub 同期ツール")
st.write("アップロードされたZIPファイルを解凍し、GitHubリポジトリのコードと自動交換します。")

# --- 画面の入力フォーム作成 ---
st.sidebar.header("🔑 設定情報")
# トークンやリポジトリ名を画面から入力できるようにする（セキュリティのためpasswordモードに）
ACCESS_TOKEN = st.sidebar.text_input(
    "GitHub Access Token", type="password", help="ghp_から始まるトークン"
)
REPO_NAME = st.sidebar.text_input("Repository", placeholder="ユーザー名/リポジトリ名")
BRANCH_NAME = st.sidebar.text_input("Branch", value="main")

# --- メイン画面：ファイルアップロード ---
uploaded_file = st.file_uploader(
    "1. テスト対象のZIPファイルをドロップしてください", type=["zip"]
)

# --- 同期処理の関数（中身はこれまでのロジックと同じ） ---
def process_and_sync(uploaded_file, token, repo_name, branch):
    g = Github(token)
    try:
        repo = g.get_repo(repo_name)
    except Exception as e:
        st.error(f"GitHubリポジトリへの接続に失敗しました: {e}")
        return

    # ZIP解凍
    zip_buffer = io.BytesIO(uploaded_file.read())
    with zipfile.ZipFile(zip_buffer, "r") as z:
        for file_path in z.namelist():
            if file_path.endswith("/"):
                continue

            with z.open(file_path) as f:
                try:
                    file_content = f.read().decode("utf-8")
                except UnicodeDecodeError:
                    st.warning(f"⚠️ テキストではないためスキップ: {file_path}")
                    continue

            commit_message = f"Update {file_path} via Web Sync Tool"

            # GitHubのファイル更新ロジック
            try:
                contents = repo.get_contents(file_path, ref=branch)
                existing_text = contents.decoded_content.decode("utf-8")

                if existing_text == file_content:
                    st.text(f"➖ 変更なし（スキップ）: {file_path}")
                    continue

                repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=file_content,
                    sha=contents.sha,
                    branch=branch,
                )
                st.success(f"✏️ 更新完了: {file_path}")

            except github.UnknownObjectException:
                repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=file_content,
                    branch=branch,
                )
                st.info(f"🆕 新規追加: {file_path}")


# --- 2. 実行ボタン ---
if uploaded_file:
    if st.button("🚀 GitHubのコードを最新状態に交換する", use_container_width=True):
        if not ACCESS_TOKEN or not REPO_NAME:
            st.error("左側のメニューから『アクセストークン』と『リポジトリ名』を入力してください。")
        else:
            with st.spinner("GitHubと同期中..."):
                process_and_sync(uploaded_file, ACCESS_TOKEN, REPO_NAME, BRANCH_NAME)
            st.balloons()  # 完了時に画面にお祝いの風船を飛ばす演出
            st.success("すべての同期処理が完了しました！")

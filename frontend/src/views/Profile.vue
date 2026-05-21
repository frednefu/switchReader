<template>
  <div class="profile">
    <div class="page-header">
      <h2>个人设置</h2>
    </div>

    <div class="profile-grid">
      <el-card class="profile-card">
        <template #header>
          <span>基本信息</span>
        </template>
        <el-form :model="form" :rules="formRules" ref="formRef" label-width="80px">
          <el-form-item label="头像">
            <div class="avatar-section">
              <el-avatar :size="64" class="profile-avatar">
                {{ authStore.user?.username?.charAt(0)?.toUpperCase() }}
              </el-avatar>
            </div>
          </el-form-item>
          <el-form-item label="用户名">
            <el-input :model-value="authStore.user?.username" disabled />
          </el-form-item>
          <el-form-item label="角色">
            <el-tag :type="authStore.isAdmin ? 'danger' : 'info'" size="small">
              {{ authStore.isAdmin ? '管理员' : '普通用户' }}
            </el-tag>
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="form.email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card class="password-card">
        <template #header>
          <span>修改密码</span>
        </template>
        <el-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef" label-width="80px">
          <el-form-item label="原密码" prop="old_password">
            <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="请输入新密码" />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleChangePassword" :loading="changingPwd">修改密码</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/store/auth'
import { updateProfile, changePassword } from '@/api/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const formRef = ref(null)
const saving = ref(false)
const form = reactive({
  email: authStore.user?.email || '',
})
const formRules = {}  // email is optional

const pwdFormRef = ref(null)
const changingPwd = ref(false)
const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirm = (_rule, value, callback) => {
  if (value !== pwdForm.new_password) {
    callback(new Error('两次密码输入不一致'))
  } else {
    callback()
  }
}

const pwdRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleSave() {
  saving.value = true
  try {
    const updated = await updateProfile({ email: form.email || null })
    authStore.user = updated
    localStorage.setItem('user', JSON.stringify(updated))
    ElMessage.success('保存成功')
  } finally {
    saving.value = false
  }
}

async function handleChangePassword() {
  try {
    await pwdFormRef.value.validate()
  } catch { return }
  changingPwd.value = true
  try {
    await changePassword(pwdForm.old_password, pwdForm.new_password)
    ElMessage.success('密码修改成功')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    pwdFormRef.value.resetFields()
  } finally {
    changingPwd.value = false
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}
.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  max-width: 900px;
}
@media (max-width: 768px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
.profile-avatar {
  background: linear-gradient(135deg, var(--color-primary), #8b5cf6);
  color: #fff;
  font-weight: 700;
  font-size: 24px;
}
</style>
